"""
安居客移动站爬虫引擎 — m.anjuke.com 按子区域分页采集。

策略: 每个子区域新建浏览器 → 逐页爬取 → 关闭浏览器 → 冷却 60-120s → 下一个
     避免同一 session 内多次请求触发 IP 限速。

与 fang.com 引擎共享 DatabasePipeline / cleaner / dedup。
"""

import asyncio
import logging
import random
import traceback

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.anjuke_constants import (
    ACTIVE_ANJUKE_AREAS,
    LIST_PAGE_TEMPLATE,
    DRY_PAGE_THRESHOLD,
    ZERO_YIELD_THRESHOLD,
    LOW_YIELD_JUMP_THRESHOLD,
    JUMP_PAGES,
    MAX_JUMPS_PER_AREA,
    FETCH_FAILURE_THRESHOLD,
    MAX_PAGES_PER_AREA,
)
from crawler.parsers.anjuke_list_parser import AnjukeListParser
from crawler.cleaner import clean_list_page_data
from crawler.dedup import compute_md5
from crawler.pipelines import DatabasePipeline

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

DB_SYNC_INTERVAL = 3
PAGE_DELAY_MIN = 3.0
PAGE_DELAY_MAX = 6.0
AREA_COOLDOWN_MIN = 60     # 子区域间最少冷却 60s
AREA_COOLDOWN_MAX = 120     # 最多 120s
IP_BLOCK_GRACE = 600        # IP 被限后的全局冷却


class AnjukeCrawlEngine:
    """安居客移动站爬虫引擎 — 每子区域独立 session。"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._status = "starting"
        self._new_count = 0
        self._updated_count = 0
        self._unchanged_count = 0
        self._error_count = 0
        self._errors: list[dict] = []
        self._district_id_map: dict[str, int] = {}
        self._current_page = 0
        self._current_area = ""

    @property
    def _running(self) -> bool:
        return self._status in ("starting", "running")

    # ── public ──────────────────────────────────────

    async def crawl_all(
        self,
        batch_type: str = "full",
        max_pages: int = 100,
        pre_created_batch_id: int | None = None,
        area_filter: list[str] | None = None,
        no_early_stop: bool = False,
    ) -> dict:
        self._status = "running"
        self._new_count = self._updated_count = self._unchanged_count = 0
        self._error_count = 0
        self._current_page = 0
        self._errors = []

        pipe = DatabasePipeline(self._session_factory)
        async with pipe as pipeline:
            self._district_id_map = await self._load_district_map(pipeline)

            areas = list(ACTIVE_ANJUKE_AREAS)
            if area_filter:
                areas = [
                    (path, db_name) for path, db_name in areas
                    if path in area_filter or db_name in area_filter
                    or any(af in path for af in area_filter)
                ]
            total_areas = len(areas)

            if pre_created_batch_id is not None:
                batch_id = pre_created_batch_id
                await pipeline.update_crawl_batch(batch_id, total_tasks=total_areas)
            else:
                batch_id = await pipeline.create_crawl_batch(
                    batch_type=batch_type, total_districts=total_areas
                )

            global_seen: set[str] = set()

            for idx, (area_path, db_name) in enumerate(areas):
                if not self._running:
                    break

                d_db_id = self._district_id_map.get(db_name, 1)
                task_id = await pipeline.create_crawl_task(batch_id, d_db_id)
                logger.info(f"[{idx+1}/{total_areas}] {area_path} ({db_name})")

                ctx = {
                    "area_path": area_path,
                    "db_name": db_name,
                    "db_id": d_db_id,
                    "task_id": task_id,
                    "page": 1,
                    "dry": 0,
                    "zero_yield": 0,
                    "jumps": 0,
                    "area_max": max_pages,
                    "yield_new": 0,
                    "yield_updated": 0,
                    "total_raw": 0,
                }

                # ── 为每个子区域新建浏览器 ──
                try:
                    async with self._make_browser() as (browser, page):
                        await self._crawl_one_area(
                            ctx, page, global_seen, pipeline, batch_id, no_early_stop
                        )
                except Exception as e:
                    logger.error(f"{area_path}: 浏览器崩溃 — {e}", exc_info=True)
                    await pipeline.finish_crawl_task(
                        task_id, "failed", error_message=f"浏览器异常: {e}"
                    )
                    continue

                # ── 子区域冷却 ──
                wait = random.randint(AREA_COOLDOWN_MIN, AREA_COOLDOWN_MAX)
                logger.info(f"  冷却 {wait}s 后进入下一个子区域...")
                await asyncio.sleep(wait)

            # ── 汇总 ──
            total_yield = self._new_count + self._updated_count
            logger.info(
                f"[Summary] 安居客爬取汇总: {total_yield} 条产出 "
                f"({self._new_count} 新 / {self._updated_count} 更新 / "
                f"{self._unchanged_count} 不变), {self._error_count} 条错误"
            )
            final_status = (
                self._status if self._status in ("failed", "stopped") else "completed"
            )
            await pipeline.finish_crawl_batch(batch_id, final_status)

        if self._status == "running":
            self._status = "completed"
        return {
            "new": self._new_count,
            "updated": self._updated_count,
            "unchanged": self._unchanged_count,
            "removed": 0,
            "errors": self._error_count,
        }

    async def _crawl_one_area(
        self, ctx, page, global_seen, pipeline, batch_id, no_early_stop
    ):
        """在单个浏览器 session 内爬取一个子区域的所有页。"""
        area_path = ctx["area_path"]
        d_db_id = ctx["db_id"]
        task_id = ctx["task_id"]

        while ctx["page"] <= ctx["area_max"] and self._running:
            p = ctx["page"]

            # ── fetch ──
            url = LIST_PAGE_TEMPLATE.format(area=area_path, page=p)
            try:
                html = await self._navigate(page, url)
            except Exception as e:
                logger.warning(f"{area_path} page {p}: 导航失败 — {e}")
                ctx["page"] += 1
                continue

            # ── IP 限速检测 ──
            if not html or len(html) < 10000:
                logger.warning(
                    f"{area_path} page {p}: IP 限速 "
                    f"(页面 {len(html) if html else 0} bytes) → 跳过该子区域"
                )
                await self._sync_db(pipeline, task_id, batch_id, page=p - 1, new_count=ctx["yield_new"])
                await pipeline.finish_crawl_task(
                    task_id, "completed",
                    error_message=f"IP 限速 page {p} ({len(html) if html else 0} bytes)",
                )
                return

            # ── parse ──
            new_n, updated_n, raw_count = await self._process_page(
                html, global_seen, pipeline, batch_id, url,
                default_district_id=d_db_id,
            )
            self._current_page = p
            ctx["yield_new"] += new_n
            ctx["yield_updated"] += updated_n
            ctx["total_raw"] += raw_count

            # ── 第 1 页诊断 ──
            if p == 1:
                if raw_count == 0:
                    logger.warning(f"{area_path}: 第 1 页无数据 → 跳过")
                    await self._sync_db(pipeline, task_id, batch_id, page=1, new_count=0)
                    await pipeline.finish_crawl_task(task_id, "completed")
                    return

                real_max = AnjukeListParser.parse_max_page(html)
                if real_max > 0:
                    ctx["area_max"] = min(ctx["area_max"], real_max)
                    logger.info(f"{area_path}: 实际最大页={real_max}, 上限={ctx['area_max']}")

            # ── DRY 检测 ──
            if not no_early_stop and raw_count == 0:
                ctx["dry"] += 1
                ctx["zero_yield"] += 1
                if ctx["dry"] >= DRY_PAGE_THRESHOLD:
                    logger.info(f"{area_path}: 连续 {DRY_PAGE_THRESHOLD} 页无数据 → 完成")
                    await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                    await pipeline.finish_crawl_task(task_id, "completed")
                    return
            else:
                ctx["dry"] = 0

            # ── 零产出检测 ──
            if not no_early_stop:
                if raw_count > 0 and new_n == 0 and updated_n == 0:
                    ctx["zero_yield"] += 1
                    if (
                        ctx["zero_yield"] >= LOW_YIELD_JUMP_THRESHOLD
                        and ctx["zero_yield"] < ZERO_YIELD_THRESHOLD
                        and ctx["jumps"] < MAX_JUMPS_PER_AREA
                    ):
                        skip_to = min(p + JUMP_PAGES, ctx["area_max"] + 1)
                        if skip_to > p:
                            logger.info(
                                f"  [Jump] {area_path}: 零产出 page {p} → {skip_to}"
                            )
                            ctx["page"] = skip_to
                            ctx["zero_yield"] = 0
                            ctx["jumps"] += 1
                            continue
                    if ctx["zero_yield"] >= ZERO_YIELD_THRESHOLD:
                        logger.info(f"{area_path}: 连续 {ctx['zero_yield']} 页零产出 → 完成")
                        await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                        await pipeline.finish_crawl_task(task_id, "completed")
                        return
                else:
                    if new_n > 0 or updated_n > 0:
                        ctx["zero_yield"] = 0

            # ── DB 同步 ──
            if p % DB_SYNC_INTERVAL == 0:
                await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])

            ctx["page"] += 1

        # ── 该子区域翻完了 ──
        await self._sync_db(pipeline, task_id, batch_id, page=ctx["page"] - 1, new_count=ctx["yield_new"])
        await pipeline.finish_crawl_task(task_id, "completed")
        logger.info(
            f"[OK] {area_path}: {ctx['page']-1} 页, 新增 {ctx['yield_new']}, "
            f"更新 {ctx['yield_updated']}"
        )

    # ── browser helper ──────────────────────────────

    async def _make_browser(self):
        """创建独立浏览器 session（轻量反检测）。"""
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )
        page = await ctx.new_page()
        page.set_default_timeout(30_000)

        class _Session:
            async def __aenter__(self2):
                return browser, page

            async def __aexit__(self2, *args):
                for obj in [page, ctx, browser, p]:
                    try:
                        c = obj.close() if hasattr(obj, "close") else obj.stop()
                        if asyncio.iscoroutine(c):
                            await c
                    except Exception:
                        pass

        return _Session()

    async def _navigate(self, page, url: str) -> str:
        """导航到 URL — 单次尝试，不重试。"""
        # 页间延迟
        delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
        await asyncio.sleep(delay)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            await asyncio.sleep(1.5)
            return await page.content()
        except Exception as e:
            logger.warning(f"导航失败: {url} — {e}")
            return ""

    # ── DB helpers ──────────────────────────────────

    async def _sync_db(self, pipeline, task_id, batch_id, page=None, new_count=None):
        try:
            page_val = page if page is not None else self._current_page
            await pipeline.update_crawl_task(
                task_id,
                page_end=page_val,
                listings_found=new_count if new_count is not None else self._new_count,
            )
            await pipeline.update_crawl_batch(
                batch_id,
                new_listings=self._new_count,
                updated_listings=self._updated_count,
            )
        except Exception as e:
            logger.warning(f"DB 同步失败: {e}")

    async def _process_page(
        self, html, global_seen, pipeline, batch_id, url, default_district_id=1
    ) -> tuple[int, int, int]:
        if not html or len(html) < 500:
            return 0, 0, 0

        listings = AnjukeListParser.parse_listing_data(html)
        if not listings:
            return 0, 0, 0

        raw_count = len(listings)
        to_insert: list[tuple[dict, int]] = []
        page_ids = set()

        for li in listings:
            hid = li.get("house_id", "")
            if not hid:
                continue
            if hid in page_ids or hid in global_seen:
                continue
            page_ids.add(hid)
            to_insert.append((li, default_district_id))

        if not to_insert:
            return 0, 0, raw_count

        for li, _ in to_insert:
            global_seen.add(li["house_id"])

        page_new = 0
        page_updated = 0
        for li, did in to_insert:
            action = await self._insert_one(pipeline, li, did, batch_id, url)
            if action == "new":
                self._new_count += 1
                page_new += 1
            elif action == "updated":
                self._updated_count += 1
                page_updated += 1
            elif action == "unchanged":
                self._unchanged_count += 1
            else:
                self._unchanged_count += 1

        await pipeline.flush()
        return page_new, page_updated, raw_count

    async def _insert_one(self, pipeline, data, district_id, batch_id, source_url) -> str:
        hid = data.get("house_id", "")
        if not hid:
            return "skip"
        try:
            cleaned = clean_list_page_data(data)
            md5 = compute_md5(cleaned)
            cid = None
            if cleaned.get("community_name"):
                cid = await pipeline.upsert_community(
                    cleaned["community_name"], district_id, None
                )
            _, action = await pipeline.upsert_listing(
                data=cleaned,
                external_id=f"ajk_{hid}",
                district_id=district_id,
                community_id=cid,
                md5_hash=md5,
                batch_id=batch_id,
                source_url=source_url,
            )
            return action
        except Exception as e:
            self._error_count += 1
            self._errors.append({"house_id": hid, "error": str(e)})
            logger.warning(f"入库失败 [{hid}]: {e}")
            return "skip"

    def stop(self) -> None:
        if self._status in ("starting", "running"):
            self._status = "stopped"

    def get_progress(self) -> dict:
        return {
            "status": self._status,
            "running": self._running,
            "new": self._new_count,
            "updated": self._updated_count,
            "errors": self._error_count,
            "current_page": self._current_page,
            "current_area": self._current_area,
        }

    @staticmethod
    async def _load_district_map(pipeline) -> dict[str, int]:
        from app.models.district import District
        r = await pipeline._write_session.execute(select(District))
        return {d.name: d.id for d in r.scalars().all()}
