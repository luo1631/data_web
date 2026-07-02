"""Playwright 爬虫引擎 — cq.esf.fang.com 按区县筛选分页采集。

每个区县独立翻页（/house-a{code}/i3{N}/），无滑块验证。
38 个区县中 28 个有 fang.com 编码、可独立爬取。
"""

import asyncio
import logging
import traceback

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.constants import (
    ACTIVE_DISTRICTS, DRY_PAGE_THRESHOLD, FETCH_FAILURE_THRESHOLD, DETAIL_URL_TEMPLATE,
)
from crawler.district_resolver import DistrictResolver
from crawler.playwright_fetcher import PlaywrightFetcher
from crawler.parsers import ListParser
from crawler.cleaner import clean_list_page_data
from crawler.dedup import compute_md5
from crawler.pipelines import DatabasePipeline

logger = logging.getLogger(__name__)

DB_SYNC_INTERVAL = 3  # 每 N 页同步一次 DB（区县模式下每页数据量更大）


class CrawlEngine:

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._status = "starting"
        self._new_count = 0
        self._updated_count = 0
        self._unchanged_count = 0
        self._error_count = 0
        self._errors: list[dict] = []
        self._district_id_map: dict[str, int] = {}
        self._resolver: DistrictResolver | None = None
        self._current_page = 0
        self._current_district = ""

    @property
    def _running(self) -> bool:
        return self._status in ("starting", "running")

    # ── public ──────────────────────────────────────

    async def crawl_all(
        self,
        batch_type: str = "full",
        max_pages: int = 30,
        pre_created_batch_id: int | None = None,
        district_filter: list[str] | None = None,
    ) -> dict:
        """按区县逐页爬取。

        Args:
            batch_type: "full" 或 "incremental"
            max_pages: 每个区县的最大翻页数
            pre_created_batch_id: 复用已创建的批次 ID
            district_filter: 限定区县名列表，None 为全部有效区县
        """
        self._status = "running"
        self._new_count = self._updated_count = self._unchanged_count = 0
        self._error_count = 0
        self._current_page = 0
        self._errors = []

        pipe = DatabasePipeline(self._session_factory)
        async with pipe as pipeline:
            self._district_id_map = await self._load_district_map(pipeline)
            self._resolver = DistrictResolver().load(self._district_id_map)

            # 筛选要爬的区县
            districts = ACTIVE_DISTRICTS
            if district_filter:
                districts = [d for d in districts if d["name"] in district_filter]

            total_districts = len(districts)

            # 创建批次
            if pre_created_batch_id is not None:
                batch_id = pre_created_batch_id
                await pipeline.update_crawl_batch(batch_id, total_tasks=total_districts)
            else:
                batch_id = await pipeline.create_crawl_batch(batch_type=batch_type, total_districts=total_districts)

            global_seen: set[str] = set()

            # 区县任务队列（支持轮转）：遇反爬暂停→跳到下一个→回头补
            # 每个区县: {district_info, task_id, page, dry, captcha_strikes,
            #             connection_strikes, district_max, paused_until}
            district_queue: list[dict] = []
            for d in districts:
                district_queue.append({
                    "district": d,
                    "task_id": None,
                    "page": 1,
                    "dry": 0,
                    "captcha_strikes": 0,
                    "connection_strikes": 0,
                    "district_max": max_pages,
                    "paused_until": 0.0,
                    "completed": False,
                })

            try:
                async with PlaywrightFetcher(headless=True) as pf:
                    active_count = len(district_queue)

                    while active_count > 0 and self._running:
                        made_progress = False

                        for idx, ctx in enumerate(district_queue):
                            if ctx["completed"]:
                                continue
                            if not self._running:
                                break

                            # 反爬冷却中 → 跳过，等时间到了再试
                            now_t = asyncio.get_running_loop().time()
                            if now_t < ctx["paused_until"]:
                                continue

                            d = ctx["district"]
                            d_name = d["name"]
                            d_code = d["fang_code"]
                            d_db_name = d.get("db_name", d_name)
                            d_db_id = self._district_id_map.get(d_db_name, 1)

                            # 首次：创建 task
                            if ctx["task_id"] is None:
                                ctx["task_id"] = await pipeline.create_crawl_task(batch_id, d_db_id)
                                logger.info(f"[{idx+1}/{total_districts}] {d_name} ({d_code})")

                            self._current_district = d_name
                            task_id = ctx["task_id"]
                            p = ctx["page"]

                            # ── fetch ──
                            try:
                                html, url = await pf.fetch_page(page=p, fang_code=d_code)
                            except Exception as e:
                                logger.error(f"{d_name} page {p}: {e}")
                                self._current_page = p
                                ctx["connection_strikes"] += 1
                                if ctx["connection_strikes"] <= 3:
                                    # 指数退避: 30s → 60s → 120s，每轮轮流爬其他区县
                                    pause_sec = 30 * (2 ** (ctx["connection_strikes"] - 1))
                                    logger.warning(
                                        f"{d_name}: paused at page {p}, "
                                        f"retry in {pause_sec}s (strike {ctx['connection_strikes']}/3)"
                                    )
                                    ctx["paused_until"] = now_t + pause_sec
                                    await self._sync_db(pipeline, task_id, batch_id)
                                    continue  # 跳到下一个区县
                                logger.error(f"{d_name}: too many resets, skipping")
                                ctx["completed"] = True
                                active_count -= 1
                                await pipeline.finish_crawl_task(task_id, "failed")
                                continue

                            ctx["connection_strikes"] = 0
                            ctx["paused_until"] = 0.0

                            # ── captcha ──
                            if PlaywrightFetcher.is_captcha_page(html):
                                ctx["captcha_strikes"] += 1
                                if ctx["captcha_strikes"] >= 5:
                                    logger.error(f"{d_name}: too many captchas, skipping")
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await pipeline.finish_crawl_task(task_id, "failed")
                                    continue
                                pause = 30 * ctx["captcha_strikes"]
                                logger.warning(f"{d_name} page {p}: captcha, skip {pause}s")
                                ctx["paused_until"] = now_t + pause
                                continue  # 跳下一个区县

                            # ── empty ──
                            if not html or len(html) < 500:
                                ctx["connection_strikes"] += 1
                                if ctx["connection_strikes"] <= 3:
                                    ctx["paused_until"] = now_t + 60 * ctx["connection_strikes"]
                                    continue
                                ctx["completed"] = True
                                active_count -= 1
                                continue

                            # ── process ──
                            new_n, updated_n, raw_count = await self._process_page(
                                html, global_seen, pipeline, batch_id, url, default_district_id=d_db_id,
                            )
                            self._current_page = p
                            made_progress = True
                            ctx["captcha_strikes"] = 0

                            # 第一页：cap district_max
                            if p == 1 and ctx["district_max"] == max_pages:
                                real_max = ListParser.parse_max_page(html)
                                if real_max > 0:
                                    ctx["district_max"] = min(max_pages, real_max)
                                    logger.info(f"{d_name}: real max page={real_max}, cap to {ctx['district_max']}")
                                elif raw_count == 0:
                                    logger.info(f"{d_name}: single empty page → done")
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await pipeline.finish_crawl_task(task_id, "completed")
                                    continue

                            # DRY
                            if raw_count == 0:
                                ctx["dry"] += 1
                                if ctx["dry"] >= DRY_PAGE_THRESHOLD:
                                    logger.info(f"{d_name} page {p}: stale → done")
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await pipeline.finish_crawl_task(task_id, "completed")
                                    continue
                            else:
                                ctx["dry"] = 0

                            if p % DB_SYNC_INTERVAL == 0:
                                await self._sync_db(pipeline, task_id, batch_id)

                            ctx["page"] += 1

                            # 该区县翻完了
                            if ctx["page"] > ctx["district_max"]:
                                ctx["completed"] = True
                                active_count -= 1
                                await self._sync_db(pipeline, task_id, batch_id)
                                await pipeline.finish_crawl_task(task_id, "completed")
                                logger.info(
                                    f"{d_name}: done ({ctx['page']-1} pages, "
                                    f"total {self._new_count} new / {self._updated_count} updated)"
                                )

                        # 一轮结束：所有区县都 pause 中或已完成
                        if not made_progress and active_count > 0:
                            # 所有活区县都在冷却 → 等 30s 再轮询
                            logger.debug(f"All districts paused/cooling, waiting 30s...")
                            await asyncio.sleep(30)

            except asyncio.CancelledError:
                if self._status == "running":
                    self._status = "stopped"
                raise
            except Exception as e:
                logger.error(f"Crawl fatal: {e}", exc_info=True)
                self._errors.append({"error": str(e), "traceback": traceback.format_exc()})
                if self._status == "running":
                    self._status = "failed"
            finally:
                final_status = self._status if self._status in ("failed", "stopped") else "completed"
                await pipeline.finish_crawl_batch(batch_id, final_status)

        if self._status == "running":
            self._status = "completed"
        return {
            "new": self._new_count, "updated": self._updated_count,
            "unchanged": self._unchanged_count, "removed": 0, "errors": self._error_count,
        }

    async def _sync_db(self, pipeline, task_id, batch_id):
        try:
            await pipeline.update_crawl_task(
                task_id, page_end=self._current_page, listings_found=self._new_count)
            await pipeline.update_crawl_batch(
                batch_id, new_listings=self._new_count, updated_listings=self._updated_count)
        except Exception as e:
            logger.warning(f"DB sync failed (non-fatal): {e}")

    # ── page processing ─────────────────────────────

    async def _process_page(self, html, global_seen, pipeline, batch_id, url, default_district_id=1) -> tuple[int, int, int]:
        if not html or len(html) < 500:
            logger.warning(f"  _process_page: HTML too short ({len(html) if html else 0} bytes), likely captcha or empty")
            return 0, 0, 0
        listings = ListParser.parse_listing_data(html)
        if not listings:
            dl_count = html.count('data-bg') if html else 0
            link_count = html.count('/chushou/') if html else 0
            logger.warning(
                f"  _process_page: 0 listings parsed from HTML "
                f"(html={len(html)} bytes, data-bg={dl_count}, /chushou/={link_count})"
            )
            return 0, 0, 0

        # raw_count: 此页 HTML 中解析出的房源条数（去重前），
        # 用于区分「页面无数据」和「页面有数据但全部未变化」两种场景
        raw_count = len(listings)

        to_insert: list[tuple[dict, int]] = []
        page_ids = set()
        skipped_seen = 0
        for li in listings:
            hid = li.get("house_id", "")
            if not hid:
                continue
            if hid in page_ids or hid in global_seen:
                skipped_seen += 1
                continue
            page_ids.add(hid)
            to_insert.append((li, self._resolve_district(li, default_district_id)))

        if skipped_seen:
            logger.info(
                f"  _process_page: {raw_count} parsed, {skipped_seen} skipped (already seen), "
                f"{len(to_insert)} to insert"
            )

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
            elif action == "skip":
                self._unchanged_count += 1

        await pipeline.flush()
        return page_new, page_updated, raw_count

    # ── insert ──────────────────────────────────────

    async def _insert_one(self, pipeline, data, district_id, batch_id, source_url) -> str:
        hid = data.get("house_id", "")
        if not hid:
            return "skip"
        try:
            cleaned = clean_list_page_data(data)
            md5 = compute_md5(cleaned)
            cid = None
            if cleaned.get("community_name"):
                cid = await pipeline.upsert_community(cleaned["community_name"], district_id, None)

            _, action = await pipeline.upsert_listing(
                data=cleaned, external_id=hid, district_id=district_id,
                community_id=cid, md5_hash=md5, batch_id=batch_id,
                source_url=source_url or DETAIL_URL_TEMPLATE.format(house_id=hid),
            )
            return action
        except Exception as e:
            self._error_count += 1
            self._errors.append({"house_id": hid, "error": str(e)})
            logger.warning(f"Insert failed [{hid}]: {e}")
            return "skip"

    # ── district ────────────────────────────────────

    def _resolve_district(self, data: dict, default_id: int = 1) -> int:
        """返回房源所属区县 DB ID。

        当前所有爬取均已按 fang_code 区县筛选，页面内房源必然属于该区县。
        文本推断仅做辅助校验，不覆盖 default_id。
        """
        return default_id

    # ── helpers ─────────────────────────────────────

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
            "current_district": self._current_district,
        }

    @staticmethod
    async def _load_district_map(pipeline) -> dict[str, int]:
        from app.models.district import District
        r = await pipeline._write_session.execute(select(District))
        return {d.name: d.id for d in r.scalars().all()}
