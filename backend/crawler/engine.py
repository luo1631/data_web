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

            try:
                async with PlaywrightFetcher(headless=True) as pf:
                    for d_idx, district in enumerate(districts):
                        if not self._running:
                            break
                        d_name = district["name"]
                        d_code = district["fang_code"]
                        d_db_id = self._district_id_map.get(d_name, 1)

                        self._current_district = d_name
                        self._current_page = 0

                        # 为每个区县创建独立 task
                        task_id = await pipeline.create_crawl_task(batch_id, d_db_id)

                        page = 1
                        dry = 0
                        district_max = max_pages  # 将被第一页实际总页数缩小

                        logger.info(f"[{d_idx+1}/{total_districts}] {d_name} ({d_code})")

                        while page <= district_max and self._running:
                            try:
                                html, url = await pf.fetch_page(page=page, fang_code=d_code)
                            except Exception as e:
                                logger.error(f"{d_name} page {page}: fetch failed — {e}")
                                self._current_page = page
                                dry += 1
                                if dry >= FETCH_FAILURE_THRESHOLD:
                                    break
                                page += 1
                                continue

                            new_n, updated_n = await self._process_page(
                                html, global_seen, pipeline, batch_id, url, default_district_id=d_db_id,
                            )
                            self._current_page = page

                            # 第一页：从翻页栏读取实际总页数，缩小上限
                            if page == 1 and district_max == max_pages:
                                real_max = ListParser.parse_max_page(html)
                                if real_max > 0:
                                    district_max = min(district_max, real_max)
                                    logger.info(f"{d_name}: real max page={real_max}, cap to {district_max}")
                                elif new_n + updated_n == 0:
                                    # 无翻页栏 + 无数据 → 1 页空区县，直接跳过
                                    logger.info(f"{d_name}: single empty page → done")
                                    break

                            if new_n + updated_n == 0:
                                dry += 1
                                if dry >= DRY_PAGE_THRESHOLD:
                                    logger.info(f"{d_name} page {page}: stale → done")
                                    break
                            else:
                                dry = 0

                            if page % DB_SYNC_INTERVAL == 0:
                                await self._sync_db(pipeline, task_id, batch_id)

                            page += 1

                        # 区县结束：同步并标记 task 完成
                        await self._sync_db(pipeline, task_id, batch_id)
                        task_status = "completed" if self._running else "stopped"
                        await pipeline.finish_crawl_task(task_id, task_status)
                        logger.info(
                            f"{d_name}: done ({self._current_page} pages, "
                            f"total {self._new_count} new / {self._updated_count} updated)"
                        )

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

    async def _process_page(self, html, global_seen, pipeline, batch_id, url, default_district_id=1) -> tuple[int, int]:
        if not html or len(html) < 500:
            return 0, 0
        listings = ListParser.parse_listing_data(html)
        if not listings:
            return 0, 0

        to_insert: list[tuple[dict, int]] = []
        page_ids = set()
        for li in listings:
            hid = li.get("house_id", "")
            if not hid or hid in page_ids or hid in global_seen:
                continue
            page_ids.add(hid)
            to_insert.append((li, self._resolve_district(li, default_district_id)))

        if not to_insert:
            return 0, 0

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
        return page_new, page_updated

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
        """从房源文本推断区县归属，以当前 fang_code 筛选的区县为默认。"""
        title = data.get("title", "") or ""
        comm = data.get("community_name", "") or ""
        addr = data.get("community_address", "") or ""
        text = f"{title} {comm} {addr}"
        name = self._resolver.resolve(text, default=None)
        if name and name in self._district_id_map:
            return self._district_id_map[name]
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
