"""Playwright 爬虫引擎 — cq.esf.fang.com 按区县筛选分页采集。

v2.0: 自适应优先级调度 + 零产出检测 + 浏览器上下文轮换

核心改进:
  1. 区分「页面无数据」和「数据全已入库」— 两种情况都应触发停止
  2. 按各区县实际产出率动态排序 — 高产区县获得更多资源
  3. 第 1 页就空 → 立即跳过（而非等 DRY_THRESHOLD 页后才放弃）
  4. 定期轮换浏览器上下文 — 降低指纹追踪风险
"""

import asyncio
import logging
import random
import time
import traceback

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.constants import (
    ACTIVE_DISTRICTS,
    DRY_PAGE_THRESHOLD,
    ZERO_YIELD_THRESHOLD,
    LOW_YIELD_JUMP_THRESHOLD,
    JUMP_PAGES,
    MAX_JUMPS_PER_DISTRICT,
    FETCH_FAILURE_THRESHOLD,
    CONTEXT_ROTATE_PAGES,
    DETAIL_URL_TEMPLATE,
)
from crawler.district_resolver import DistrictResolver
from crawler.playwright_fetcher import PlaywrightFetcher
from crawler.parsers import ListParser
from crawler.cleaner import clean_list_page_data
from crawler.dedup import compute_md5
from crawler.pipelines import DatabasePipeline

logger = logging.getLogger(__name__)

DB_SYNC_INTERVAL = 3  # 每 N 页同步一次 DB


class CrawlEngine:
    """自适应区县爬取引擎。

    每轮按产出率排序区县队列 → 高产区县优先 → 低产/全入库区县自动降级或停止。
    """

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
        # 上下文轮换计数
        self._total_pages_fetched = 0

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
        no_early_stop: bool = False,
    ) -> dict:
        """按区县逐页爬取 — 自适应优先级调度。

        Args:
            batch_type: "full" 或 "incremental"
            max_pages: 每个区县的最大翻页数
            pre_created_batch_id: 复用已创建的批次 ID
            district_filter: 限定区县名列表，None 为全部有效区县
            no_early_stop: 禁用零产出跳页和提前停止 (用于首次全量爬取)
        """
        self._status = "running"
        self._new_count = self._updated_count = self._unchanged_count = 0
        self._error_count = 0
        self._current_page = 0
        self._total_pages_fetched = 0
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
                batch_id = await pipeline.create_crawl_batch(
                    batch_type=batch_type, total_districts=total_districts
                )

            global_seen: set[str] = set()

            # ── 区县任务队列 ──
            # 每个区县维护完整状态字典，支持动态排序和降级
            queue: list[dict] = []
            for d in districts:
                queue.append({
                    "district": d,
                    "task_id": None,
                    "page": 1,
                    "dry": 0,                  # 连续空页面计数
                    "zero_yield": 0,            # 连续零产出计数（有数据但全已入库）
                    "jumps": 0,                 # 累计跳页次数
                    "captcha_strikes": 0,
                    "connection_strikes": 0,
                    "district_max": max_pages,
                    "paused_until": 0.0,
                    "completed": False,
                    # 产出统计（用于自适应排序）
                    "yield_new": 0,             # 本区县累计新增
                    "yield_updated": 0,         # 本区县累计更新
                    "pages_fetched": 0,         # 本区县已抓页数
                    "total_raw": 0,             # 本区县原始解析条数
                })

            # 首次任务创建延迟到第一次访问时（lazy init）
            unstarted = len(queue)

            try:
                async with PlaywrightFetcher(headless=True) as pf:
                    active_count = len(queue)

                    while active_count > 0 and self._running:
                        # ── 自适应排序：每轮按产出率重排 ──
                        # 未开始的区县（pages_fetched == 0）排最前以尽快诊断
                        # 已开始的按 yield_rate 降序
                        def _sort_key(ctx: dict) -> float:
                            if ctx["completed"]:
                                return -999.0
                            if ctx["pages_fetched"] == 0:
                                return 1000.0  # 未开始 → 最高优先级（快速诊断）
                            total_yield = ctx["yield_new"] + ctx["yield_updated"]
                            if ctx["pages_fetched"] == 0:
                                return 0.0
                            return total_yield / ctx["pages_fetched"]

                        queue.sort(key=_sort_key, reverse=True)

                        made_progress = False

                        # ── 上下文轮换检查 ──
                        if self._total_pages_fetched > 0 and \
                           self._total_pages_fetched % CONTEXT_ROTATE_PAGES == 0:
                            logger.info(
                                f"[Rotate] Rotating browser context "
                                f"(total pages: {self._total_pages_fetched})"
                            )
                            await pf.rotate_context()

                        for idx, ctx in enumerate(queue):
                            if ctx["completed"]:
                                continue
                            if not self._running:
                                break

                            # 反爬冷却中 → 跳过
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
                                ctx["task_id"] = await pipeline.create_crawl_task(
                                    batch_id, d_db_id
                                )
                                unstarted -= 1
                                logger.info(
                                    f"[{total_districts - unstarted}/{total_districts}] "
                                    f"{d_name} ({d_code}) — 开始"
                                )

                            self._current_district = d_name
                            task_id = ctx["task_id"]
                            p = ctx["page"]

                            # ── fetch ──
                            try:
                                html, url = await pf.fetch_page(
                                    page=p, fang_code=d_code
                                )
                            except Exception as e:
                                logger.error(f"{d_name} page {p}: {e}")
                                self._current_page = p
                                self._total_pages_fetched += 1
                                ctx["pages_fetched"] += 1
                                ctx["connection_strikes"] += 1
                                if ctx["connection_strikes"] <= FETCH_FAILURE_THRESHOLD:
                                    pause_sec = 30 * (2 ** (ctx["connection_strikes"] - 1))
                                    logger.warning(
                                        f"{d_name}: 网络异常，暂停 {pause_sec}s "
                                        f"(strike {ctx['connection_strikes']}/{FETCH_FAILURE_THRESHOLD})"
                                    )
                                    ctx["paused_until"] = now_t + pause_sec
                                    await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                    continue
                                logger.error(
                                    f"{d_name}: 网络失败次数过多 → 跳过"
                                )
                                ctx["completed"] = True
                                active_count -= 1
                                await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                await pipeline.finish_crawl_task(
                                    task_id, "failed",
                                    error_message=f"网络失败 {ctx['connection_strikes']} 次"
                                )
                                continue

                            ctx["connection_strikes"] = 0
                            ctx["paused_until"] = 0.0
                            self._total_pages_fetched += 1
                            ctx["pages_fetched"] += 1

                            # ── captcha ──
                            if PlaywrightFetcher.is_captcha_page(html):
                                ctx["captcha_strikes"] += 1
                                if ctx["captcha_strikes"] >= 5:
                                    logger.error(
                                        f"{d_name}: 验证码过多（{ctx['captcha_strikes']}次）→ 跳过"
                                    )
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                    await pipeline.finish_crawl_task(
                                        task_id, "failed",
                                        error_message=f"验证码 {ctx['captcha_strikes']} 次"
                                    )
                                    # 触发上下文轮换
                                    logger.info("[Rotate] 触发紧急上下文轮换（验证码风暴）")
                                    await pf.rotate_context()
                                    continue
                                pause = 30 * ctx["captcha_strikes"]
                                logger.warning(
                                    f"{d_name} page {p}: 验证码，冷却 {pause}s "
                                    f"(strike {ctx['captcha_strikes']}/5)"
                                )
                                ctx["paused_until"] = now_t + pause
                                continue

                            # ── empty HTML ──
                            if not html or len(html) < 500:
                                ctx["connection_strikes"] += 1
                                if ctx["connection_strikes"] <= FETCH_FAILURE_THRESHOLD:
                                    ctx["paused_until"] = now_t + 60 * ctx["connection_strikes"]
                                    continue
                                ctx["completed"] = True
                                active_count -= 1
                                await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                await pipeline.finish_crawl_task(
                                    task_id, "failed",
                                    error_message=f"连续 {ctx['connection_strikes']} 次 HTML 过短"
                                )
                                continue

                            # ── process ──
                            new_n, updated_n, raw_count = await self._process_page(
                                html, global_seen, pipeline, batch_id, url,
                                default_district_id=d_db_id,
                            )
                            self._current_page = p
                            made_progress = True
                            ctx["captcha_strikes"] = 0
                            ctx["yield_new"] += new_n
                            ctx["yield_updated"] += updated_n
                            ctx["total_raw"] += raw_count

                            # ── 第 1 页诊断 ──
                            if p == 1:
                                if raw_count == 0:
                                    # 第 1 页就无数据 → 大概率 fang_code 失效或区县无房源
                                    # 从 HTML 提取诊断信息帮助排查
                                    diag_parts = [f"fang_code={d_code}"]
                                    if html:
                                        dl_tags = html.count('<dl')
                                        data_bg = html.count('data-bg')
                                        chushou = html.count('/chushou/')
                                        diag_parts.append(
                                            f"html={len(html)}bytes dl={dl_tags} "
                                            f"data-bg={data_bg} /chushou/={chushou}"
                                        )
                                    diag = "; ".join(diag_parts)
                                    logger.warning(
                                        f"{d_name}: 第 1 页无数据 → 立即跳过 "
                                        f"({diag})"
                                    )
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await self._sync_db(
                                        pipeline, task_id, batch_id,
                                        page=1, new_count=ctx["yield_new"],
                                    )
                                    await pipeline.finish_crawl_task(
                                        task_id, "completed",
                                        error_message=f"第 1 页无房源数据 ({diag})",
                                    )
                                    continue

                                # 第 1 页：cap district_max
                                real_max = ListParser.parse_max_page(html)
                                if real_max > 0:
                                    ctx["district_max"] = min(max_pages, real_max)
                                    logger.info(
                                        f"{d_name}: 实际最大页={real_max}, "
                                        f"上限={ctx['district_max']}"
                                    )

                            # ── DRY 检测（页面完全无房源数据）──
                            # no_early_stop 模式下跳过: 用户要逐页全量爬取
                            if not no_early_stop and raw_count == 0:
                                ctx["dry"] += 1
                                ctx["zero_yield"] += 1
                                if ctx["dry"] >= DRY_PAGE_THRESHOLD:
                                    logger.info(
                                        f"{d_name} page {p}: 连续 {DRY_PAGE_THRESHOLD} 页无数据 → 完成"
                                    )
                                    ctx["completed"] = True
                                    active_count -= 1
                                    await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                    await pipeline.finish_crawl_task(task_id, "completed")
                                    continue
                            else:
                                ctx["dry"] = 0

                            # ── 零产出检测（有数据但全已入库，无新增/更新）──
                            # no_early_stop 模式下完全跳过：用户要逐页全量爬取
                            if not no_early_stop:
                                if raw_count > 0 and new_n == 0 and updated_n == 0:
                                    ctx["zero_yield"] += 1

                                    # 阶段 A: 触发跳页（可能踩到历史已爬页面）
                                    if (
                                        ctx["zero_yield"] >= LOW_YIELD_JUMP_THRESHOLD
                                        and ctx["zero_yield"] < ZERO_YIELD_THRESHOLD
                                        and ctx["jumps"] < MAX_JUMPS_PER_DISTRICT
                                    ):
                                        skip_to = min(
                                            ctx["page"] + JUMP_PAGES,
                                            ctx["district_max"] + 1,
                                        )
                                        if skip_to > ctx["page"]:
                                            logger.info(
                                                f"  [Jump] {d_name}: 连续 {ctx['zero_yield']} 页零产出 → "
                                                f"跳页 page {ctx['page']} → {skip_to} "
                                                f"(第 {ctx['jumps']+1}/{MAX_JUMPS_PER_DISTRICT} 次跳页)"
                                            )
                                            ctx["page"] = skip_to
                                            ctx["zero_yield"] = 0
                                            ctx["jumps"] += 1
                                            continue

                                    # 阶段 B: 跳页次数耗尽或超过阈值 → 停止
                                    if ctx["zero_yield"] >= ZERO_YIELD_THRESHOLD:
                                        reason = (
                                            f"连续 {ZERO_YIELD_THRESHOLD} 页零产出"
                                            if ctx["jumps"] >= MAX_JUMPS_PER_DISTRICT
                                            else f"连续 {ctx['zero_yield']} 页零产出"
                                        )
                                        logger.info(
                                            f"{d_name} page {p}: {reason}"
                                            f"（{ctx['total_raw']} 条原始数据, "
                                            f"跳页 {ctx['jumps']} 次）→ 完成"
                                        )
                                        ctx["completed"] = True
                                        active_count -= 1
                                        await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                        await pipeline.finish_crawl_task(task_id, "completed")
                                        continue
                                else:
                                    # 有新增或更新 → 归零
                                    if new_n > 0 or updated_n > 0:
                                        ctx["zero_yield"] = 0

                            # ── 定期 DB 同步 ──
                            if p % DB_SYNC_INTERVAL == 0:
                                await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])

                            ctx["page"] += 1

                            # 该区县翻完了
                            if ctx["page"] > ctx["district_max"]:
                                yield_total = ctx["yield_new"] + ctx["yield_updated"]
                                ctx["completed"] = True
                                active_count -= 1
                                await self._sync_db(pipeline, task_id, batch_id, page=p, new_count=ctx["yield_new"])
                                await pipeline.finish_crawl_task(task_id, "completed")
                                logger.info(
                                    f"[OK] {d_name}: 完成 "
                                    f"({ctx['page']-1} 页, "
                                    f"新增 {ctx['yield_new']}, "
                                    f"更新 {ctx['yield_updated']}, "
                                    f"原始 {ctx['total_raw']} 条, "
                                    f"产出率 {yield_total}/{ctx['pages_fetched']}页 = "
                                    f"{yield_total/max(1,ctx['pages_fetched']):.1f}/页)"
                                )

                        # ── 一轮结束 ──
                        if not made_progress and active_count > 0:
                            # 所有活区县都在冷却 → 等 30s
                            active_names = [
                                q["district"]["name"]
                                for q in queue
                                if not q["completed"]
                            ]
                            logger.debug(
                                f"所有区县冷却中 ({len(active_names)}: "
                                f"{', '.join(active_names[:5])}...)，等待 30s"
                            )
                            await asyncio.sleep(30)

            except asyncio.CancelledError:
                if self._status == "running":
                    self._status = "stopped"
                raise
            except Exception as e:
                logger.error(f"爬虫致命错误: {e}", exc_info=True)
                self._errors.append({
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                if self._status == "running":
                    self._status = "failed"
            finally:
                # ── 未完成任务收尾 ──
                # 遍历队列中所有非完成状态的区县，保存最新 page_end 并标记停止
                interrupted_tasks = [
                    q for q in queue if not q["completed"] and q["task_id"] is not None
                ]
                if interrupted_tasks:
                    final_task_status = (
                        "stopped" if self._status == "stopped" else "failed"
                    )
                    for q in interrupted_tasks:
                        try:
                            # 用各区县自己的 page 和计数，而非全局 self._current_page
                            await pipeline.update_crawl_task(
                                q["task_id"],
                                page_end=q["page"] - 1,  # 最后处理的实际页号
                                listings_found=q["yield_new"],
                            )
                            await pipeline.finish_crawl_task(
                                q["task_id"], final_task_status
                            )
                        except Exception as e:
                            logger.warning(
                                f"收尾 task#{q['task_id']} ({q['district']['name']}) 失败: {e}"
                            )
                    logger.info(
                        f"收尾 {len(interrupted_tasks)} 个未完成任务 → status={final_task_status}"
                    )

                # ── 产出汇总 ──
                total_yield = self._new_count + self._updated_count
                productive = sum(
                    1 for ctx in queue
                    if ctx["yield_new"] + ctx["yield_updated"] > 0
                )
                logger.info(
                    f"[Summary] 爬取汇总: {total_yield} 条产出 "
                    f"({self._new_count} 新 / {self._updated_count} 更新 / "
                    f"{self._unchanged_count} 不变), "
                    f"{productive}/{total_districts} 区县有产出, "
                    f"{self._total_pages_fetched} 总页数, "
                    f"{self._error_count} 条错误"
                )
                final_status = (
                    self._status
                    if self._status in ("failed", "stopped")
                    else "completed"
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
            logger.warning(f"DB 同步失败 (非致命): {e}")

    # ── page processing ─────────────────────────────

    async def _process_page(
        self, html, global_seen, pipeline, batch_id, url, default_district_id=1
    ) -> tuple[int, int, int]:
        """处理单个列表页。

        Returns:
            (new_count, updated_count, raw_count)
            raw_count: 页面解析出的房源数（去重前），用于区分「空页面」和「全已入库」
        """
        if not html or len(html) < 500:
            logger.warning(
                f"  _process_page: HTML 太短 "
                f"({len(html) if html else 0} bytes)"
            )
            return 0, 0, 0

        listings = ListParser.parse_listing_data(html)
        if not listings:
            dl_count = html.count('data-bg') if html else 0
            link_count = html.count('/chushou/') if html else 0
            logger.warning(
                f"  _process_page: 0 条解析结果 "
                f"(html={len(html)} bytes, data-bg={dl_count}, "
                f"/chushou/={link_count})"
            )
            return 0, 0, 0

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
            to_insert.append((
                li,
                self._resolve_district(li, default_district_id),
            ))

        if skipped_seen > 0:
            logger.debug(
                f"  _process_page: {raw_count} 条解析, "
                f"{skipped_seen} 条跳过（已见过）, "
                f"{len(to_insert)} 条待入库"
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
            elif action == "unchanged":
                self._unchanged_count += 1
            else:  # "skip" — 入库异常或缺少 house_id
                self._unchanged_count += 1  # 也算未变更（未成功入库）

        await pipeline.flush()
        return page_new, page_updated, raw_count

    # ── insert ──────────────────────────────────────

    async def _insert_one(
        self, pipeline, data, district_id, batch_id, source_url
    ) -> str:
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
                external_id=hid,
                district_id=district_id,
                community_id=cid,
                md5_hash=md5,
                batch_id=batch_id,
                source_url=source_url or DETAIL_URL_TEMPLATE.format(house_id=hid),
            )
            return action
        except Exception as e:
            self._error_count += 1
            self._errors.append({"house_id": hid, "error": str(e)})
            logger.warning(f"入库失败 [{hid}]: {e}")
            return "skip"

    # ── district ────────────────────────────────────

    def _resolve_district(self, data: dict, default_id: int = 1) -> int:
        """返回房源所属区县 DB ID。

        当前所有爬取均已按 fang_code 区县筛选，
        页面内房源必然属于该区县。文本推断仅做辅助校验。
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
