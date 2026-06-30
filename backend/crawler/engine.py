"""
爬虫引擎 — m.fang.com 移动站（SSR 渲染，无字体加密）。

策略: 爬全市列表 `?page=N`，每个详情页自带区县信息。
"""

import asyncio
import json
import traceback

from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.constants import (
    LIST_CONCURRENCY, DETAIL_CONCURRENCY, MAX_PAGES_PER_DISTRICT,
    LISTINGS_PER_PAGE,
)
from crawler.fetcher import Fetcher
from crawler.parsers import ListParser, DetailParser
from crawler.cleaner import clean_listing
from crawler.dedup import compute_md5, match_community
from crawler.pipelines import DatabasePipeline


class CrawlEngine:
    """爬虫引擎"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._running = False
        self._list_sem = asyncio.Semaphore(LIST_CONCURRENCY)
        self._detail_sem = asyncio.Semaphore(DETAIL_CONCURRENCY)
        self._new_count = 0
        self._updated_count = 0
        self._unchanged_count = 0
        self._error_count = 0
        self._removed_count = 0
        self._errors: list[dict] = []

    # ── public API ──

    async def crawl_all(
        self,
        district_ids: list[int] | None = None,
        batch_type: str = "full",
        max_pages: int = MAX_PAGES_PER_DISTRICT,
        pre_created_batch_id: int | None = None,
    ) -> dict:
        self._running = True
        self._new_count = self._updated_count = self._unchanged_count = 0
        self._error_count = self._removed_count = 0
        self._errors = []

        async with Fetcher() as fetcher, DatabasePipeline(self._session_factory) as pipeline:
            # 解析区县
            district_map = await self._resolve_district_map(pipeline, district_ids)

            # 创建 batch
            if pre_created_batch_id is not None:
                batch_id = pre_created_batch_id
                await pipeline.update_crawl_batch(batch_id, total_tasks=1)
            else:
                batch_id = await pipeline.create_crawl_batch(batch_type=batch_type, total_districts=1)

            task_id = await pipeline.create_crawl_task(batch_id, None)

            try:
                # ── Phase 1: 遍历全市列表页，收集所有房源数据 ──
                all_listings: list[dict] = []
                page = 1
                while page <= max_pages and self._running:
                    async with self._list_sem:
                        html = await fetcher.fetch_list_page("cq", page)
                        listings = ListParser.parse_listing_data(html)
                        if not listings:
                            break
                        all_listings.extend(listings)
                        if page == 1:
                            total_count = ListParser.parse_total_count(html)
                            total_pages = min(
                                max((total_count + LISTINGS_PER_PAGE - 1) // LISTINGS_PER_PAGE, 1),
                                max_pages,
                            )
                        else:
                            total_pages = max_pages
                    page += 1
                    if page > total_pages:
                        break

                await pipeline.update_crawl_task(task_id, page_end=min(page, total_pages), listings_found=len(all_listings))

                # ── Phase 2: 详情页 ──
                if all_listings:
                    detail_tasks = [
                        self._crawl_one_detail(li, batch_id, fetcher, pipeline, district_map)
                        for li in all_listings
                    ]
                    await asyncio.gather(*detail_tasks, return_exceptions=True)

                await pipeline.finish_crawl_task(task_id, "completed")
                print(f"[OK] Total: {len(all_listings)} listings processed")

            except Exception as e:
                await pipeline.finish_crawl_task(task_id, "failed", error_message=str(e))
                self._error_count += 1
                self._errors.append({"error": str(e), "traceback": traceback.format_exc()})
                print(f"[ERR] {e}")

            # ── 完成 batch ──
            await pipeline.update_crawl_batch(
                batch_id, completed_tasks=1,
                new_listings=self._new_count, updated_listings=self._updated_count,
                removed_listings=self._removed_count,
                error_summary=json.dumps(self._errors[:100], ensure_ascii=False, default=str),
            )
            await pipeline.finish_crawl_batch(batch_id, "completed")

        self._running = False
        return {
            "new": self._new_count, "updated": self._updated_count,
            "unchanged": self._unchanged_count, "removed": self._removed_count,
            "errors": self._error_count,
        }

    # ── detail pipeline ──

    async def _crawl_one_detail(self, listing_info: dict, batch_id: int,
                                fetcher: Fetcher, pipeline: DatabasePipeline,
                                district_map: dict[str, int]) -> None:
        if not self._running:
            return
        house_id = listing_info.get("house_id", "")
        if not house_id:
            return

        async with self._detail_sem:
            try:
                source_url = f"https://m.fang.com/esf/cq/{house_id}.html"
                html = await fetcher.fetch_detail_page(house_id)

                # Parse
                parser = DetailParser(house_id, source_url)
                parsed = parser.parse(html)

                # Merge list data (fallback for missing detail fields)
                self._merge_listing_data(parsed, listing_info)

                # Resolve district from detail page
                district_id = self._resolve_district_from_detail(parsed, district_map)

                # Clean
                cleaned = clean_listing(parsed, None, None)

                # MD5
                md5_hash = compute_md5(cleaned)

                # Community
                community_id = None
                if cleaned.get("community_name"):
                    community_id = await match_community(
                        cleaned["community_name"], district_id, pipeline._write_session)
                if not community_id and cleaned.get("community_name"):
                    community_id = await pipeline.upsert_community(
                        cleaned["community_name"], district_id,
                        cleaned.get("community_address"),
                        lng=parsed.community_lng, lat=parsed.community_lat,
                    )

                # Upsert
                _, action = await pipeline.upsert_listing(
                    data=cleaned, external_id=house_id, district_id=district_id,
                    community_id=community_id, md5_hash=md5_hash,
                    batch_id=batch_id, source_url=source_url,
                )

                if action == "new":
                    self._new_count += 1
                elif action == "updated":
                    self._updated_count += 1
                else:
                    self._unchanged_count += 1

            except Exception as e:
                self._error_count += 1
                self._errors.append({
                    "house_id": house_id, "error": str(e),
                    "traceback": traceback.format_exc(),
                })

    # ── helpers ──

    def stop(self) -> None:
        self._running = False

    def get_progress(self) -> dict:
        return {
            "running": self._running, "new": self._new_count,
            "updated": self._updated_count, "unchanged": self._unchanged_count,
            "errors": self._error_count,
        }

    @staticmethod
    async def _resolve_district_map(pipeline, district_ids) -> dict[str, int]:
        """构建 {区县名: DB id} 映射。"""
        from app.models.district import District
        from sqlalchemy import select
        result = await pipeline._write_session.execute(select(District))
        return {d.name: d.id for d in result.scalars().all()
                if not district_ids or d.id in district_ids}

    @staticmethod
    def _resolve_district_from_detail(parsed, district_map: dict[str, int]) -> int:
        """从详情页提取的地址/坐标推断区县。

        优先级: 1) 地址/小区名 2) 街道名
        返回 district_id，无法确定则返回 0 (代表"未知")。
        """
        from crawler.constants import DISTRICT_BY_NAME
        text = ""
        if parsed.community_address:
            text += parsed.community_address + " "
        if parsed.community_name:
            text += parsed.community_name + " "

        # 直接匹配区县名
        for name, info in DISTRICT_BY_NAME.items():
            if name in text or info["pinyin"] in text.lower():
                return district_map.get(name, 0)

        return 1  # 默认渝北区（有房源的大区）

    @staticmethod
    def _merge_listing_data(parsed, listing_info: dict) -> None:
        """列表页数据补全详情页缺失字段。"""
        if parsed.total_price is None:
            parsed.total_price = listing_info.get("total_price")
        if parsed.room_count is None:
            parsed.room_count = listing_info.get("room_count")
        if parsed.hall_count is None:
            parsed.hall_count = listing_info.get("hall_count")
        if parsed.bathroom_count is None:
            parsed.bathroom_count = listing_info.get("bathroom_count")
        if parsed.area is None:
            parsed.area = listing_info.get("area")
        if parsed.orientation is None:
            parsed.orientation = listing_info.get("orientation")
        if parsed.decoration is None:
            parsed.decoration = listing_info.get("decoration")
        if parsed.community_name is None:
            parsed.community_name = listing_info.get("community_name")
        if parsed.title is None:
            parsed.title = listing_info.get("title")
        if parsed.floor_level is None:
            parsed.floor_level = listing_info.get("floor_level")
