"""
爬虫引擎：asyncio 并发编排整个爬取流程。

单区县流程:
  list pages (串行，3-5s/page) → collect IDs
  → detail pages (asyncio.gather, Semaphore(5), 2-4s/each)
  → parse → decrypt → clean → dedup → upsert

全量流程:
  crawl_district() × N → asyncio.gather（每个区县独立协程）

启停控制:
  self._running = False → 协程在当前操作完成后自然退出
"""

import asyncio
import traceback
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.constants import (
    LIST_CONCURRENCY,
    DETAIL_CONCURRENCY,
    MAX_PAGES_PER_DISTRICT,
    DISTRICT_BY_SLUG,
)
from crawler.fetcher import Fetcher
from crawler.parsers import (
    ListParser,
    DetailParser,
    FontDecryptor,
    FontNotCachedError,
)
from crawler.cleaner import clean_listing
from crawler.dedup import compute_md5, match_community
from crawler.pipelines import DatabasePipeline


class CrawlEngine:
    """爬虫引擎：编排完整的爬取→清洗→入库流程。

    用法:
        engine = CrawlEngine(async_session)
        await engine.crawl_all(district_ids=[1, 2, 3])
        # 或
        await engine.crawl_all(district_ids=None)  # 全部 38 区县
    """

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._running = False
        self._list_sem = asyncio.Semaphore(LIST_CONCURRENCY)
        self._detail_sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

        # 统计
        self._new_count = 0
        self._updated_count = 0
        self._unchanged_count = 0
        self._error_count = 0
        self._removed_count = 0
        self._errors: list[dict] = []

    # ── public API ───────────────────────────────────

    async def crawl_all(
        self,
        district_ids: list[int] | None = None,
        batch_type: str = "full",
        max_pages: int = MAX_PAGES_PER_DISTRICT,
        pre_created_batch_id: int | None = None,
    ) -> dict:
        """全量爬取入口。

        Args:
            district_ids: 指定区县数据库 ID 列表，None 表示全部
            batch_type: 批次类型 "full" / "incremental"
            max_pages: 每区县最大列表页数
            pre_created_batch_id: 如果调用方已预先创建了 CrawlBatch 记录，
                                 则传入已有的 batch_id，引擎不再重复创建。

        Returns:
            统计摘要 dict
        """
        self._running = True
        # 重置计数器（支持复用同一实例）
        self._new_count = 0
        self._updated_count = 0
        self._unchanged_count = 0
        self._error_count = 0
        self._removed_count = 0
        self._errors: list[dict] = []

        async with Fetcher() as fetcher, DatabasePipeline(
            self._session_factory
        ) as pipeline:

            districts = await self._resolve_districts(pipeline, district_ids)
            if not districts:
                return {"error": "no districts to crawl"}

            # 创建或复用爬取批次
            if pre_created_batch_id is not None:
                batch_id = pre_created_batch_id
                await pipeline.update_crawl_batch(
                    batch_id, total_tasks=len(districts)
                )
            else:
                batch_id = await pipeline.create_crawl_batch(
                    batch_type=batch_type, total_districts=len(districts)
                )

            tasks = [
                self.crawl_district(
                    db_id=d["id"],
                    name=d["name"],
                    slug=d["slug"],
                    batch_id=batch_id,
                    max_pages=max_pages,
                    fetcher=fetcher,
                    pipeline=pipeline,
                )
                for d in districts
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # 统计已完成的任务数
            completed = sum(1 for t in tasks if not t.exception())
            await pipeline.update_crawl_batch(
                batch_id,
                completed_tasks=completed,
                new_listings=self._new_count,
                updated_listings=self._updated_count,
                removed_listings=self._removed_count,
                error_summary=str(self._errors[:100]),
            )
            await pipeline.finish_crawl_batch(batch_id, "completed")

        self._running = False
        return {
            "new": self._new_count,
            "updated": self._updated_count,
            "unchanged": self._unchanged_count,
            "removed": self._removed_count,
            "errors": self._error_count,
        }

    async def crawl_district(
        self,
        db_id: int,
        name: str,
        slug: str,
        batch_id: int,
        max_pages: int,
        fetcher: Fetcher,
        pipeline: DatabasePipeline,
    ) -> None:
        """爬取单个区县的所有房源。

        1. 如果该 batch+district 已有完成的 CrawlTask → 跳过（真断点续爬）
        2. 遍历列表页 1..N，收集所有房源 ID
        3. 并发爬取每个房源的详情页
        4. 检测已下架房源
        """
        if not self._running:
            return

        # 断点续爬：已完成则跳过
        task_id = await pipeline.get_or_create_crawl_task(batch_id, db_id)
        if task_id is None:
            # 已有完成的 task → 跳过
            print(f"[SKIP] {name}: already completed in batch #{batch_id}")
            return

        try:
            # ── Phase 1: 收集房源 ID ──
            all_ids: list[str] = []

            async with self._list_sem:
                # 首页：获取总数和 ID 列表
                page = 1
                html = await fetcher.fetch_list_page(slug, page)
                total_count = ListParser.parse_total_count(html)
                ids = ListParser.parse_listing_ids(html)
                all_ids.extend(ids)

                total_pages = min(
                    ListParser.calculate_total_pages(total_count),
                    max_pages,
                )

                # 遍历剩余页
                for page in range(2, total_pages + 1):
                    if not self._running:
                        break
                    html = await fetcher.fetch_list_page(slug, page)
                    ids = ListParser.parse_listing_ids(html)
                    if not ids:
                        break  # 空页 = 已到末页
                    all_ids.extend(ids)

            # 更新任务进度
            await pipeline.update_crawl_task(
                task_id,
                page_end=total_pages,
                listings_found=len(all_ids),
            )

            # ── Phase 2: 爬取详情 ──
            if all_ids:
                detail_tasks = [
                    self._crawl_one_detail(
                        listing_id=lid,
                        district_id=db_id,
                        batch_id=batch_id,
                        fetcher=fetcher,
                        pipeline=pipeline,
                    )
                    for lid in all_ids
                ]
                await asyncio.gather(*detail_tasks, return_exceptions=True)

            # ── Phase 3: 检测下架房源 ──
            # 本区县中，在库且 active 但本次未出现的 = 已下架
            if all_ids:
                removed = await pipeline.mark_removed_listings(db_id, all_ids)
                self._removed_count += removed

            await pipeline.finish_crawl_task(task_id, "completed")
            print(f"[OK] {name}: {len(all_ids)} listings processed, {self._removed_count} removed")

        except Exception as e:
            await pipeline.finish_crawl_task(
                task_id, "failed", error_message=str(e)
            )
            self._error_count += 1
            self._errors.append({
                "district": name,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            print(f"[ERR] {name}: {e}")

    # ── stop control ─────────────────────────────────

    def stop(self) -> None:
        """发出停止信号。正在进行的操作完成后协程自然退出。"""
        self._running = False

    # ── progress ─────────────────────────────────────

    def get_progress(self) -> dict:
        return {
            "running": self._running,
            "new": self._new_count,
            "updated": self._updated_count,
            "unchanged": self._unchanged_count,
            "errors": self._error_count,
        }

    # ── internal ─────────────────────────────────────

    async def _crawl_one_detail(
        self,
        listing_id: str,
        district_id: int,
        batch_id: int,
        fetcher: Fetcher,
        pipeline: DatabasePipeline,
    ) -> None:
        """处理单条房源：获取详情 → 解析 → 解密 → 清洗 → 去重 → 入库。"""
        if not self._running:
            return

        font_decryptor = FontDecryptor()

        try:
            async with self._detail_sem:
                # 1. 获取详情页
                source_url = (
                    f"https://cq.esf.fang.com/chushou/{listing_id}.htm"
                )
                try:
                    html = await fetcher.fetch_detail_page(listing_id)
                except Exception:
                    self._error_count += 1
                    return

                # 2. 解析
                parser = DetailParser(listing_id, source_url)
                parsed = parser.parse(html)

                # 3. 字体解密
                decrypted_total = None
                decrypted_unit = None
                if parsed.font_url:
                    try:
                        await font_decryptor.load_font(
                            parsed.font_url, fetcher
                        )
                        decrypted_total = font_decryptor.decrypt(
                            parsed.total_price_raw or ""
                        )
                        decrypted_unit = font_decryptor.decrypt(
                            parsed.unit_price_raw or ""
                        )
                    except FontNotCachedError as e:
                        # 新字体 → 记录并跳过（等待人工标定后重试）
                        self._error_count += 1
                        self._errors.append({
                            "listing_id": listing_id,
                            "error": str(e),
                            "font_md5": e.font_md5,
                        })
                        return

                # 4. 清洗
                cleaned = clean_listing(parsed, decrypted_total, decrypted_unit)

                # 5. MD5
                md5_hash = compute_md5(cleaned)

                # 6. 小区匹配
                community_id = None
                if cleaned.get("community_name"):
                    community_id = await match_community(
                        cleaned["community_name"], district_id,
                        pipeline._write_session,
                    )
                if not community_id and cleaned.get("community_name"):
                    community_id = await pipeline.upsert_community(
                        cleaned["community_name"],
                        district_id,
                        cleaned.get("community_address"),
                    )

                # 7. 入库
                _, action = await pipeline.upsert_listing(
                    data=cleaned,
                    external_id=listing_id,
                    district_id=district_id,
                    community_id=community_id,
                    md5_hash=md5_hash,
                    batch_id=batch_id,
                    source_url=source_url,
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
                "listing_id": listing_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

    async def _resolve_districts(
        self, pipeline: DatabasePipeline, district_ids: list[int] | None
    ) -> list[dict]:
        """解析区县列表，合并常量与数据库 ID。"""
        from app.models.district import District
        from sqlalchemy import select

        result = await pipeline._write_session.execute(select(District))
        db_districts = {d.name: d.id for d in result.scalars().all()}

        resolved = []
        for d in DISTRICT_BY_SLUG.values():
            db_id = db_districts.get(d["name"])
            if db_id is None:
                continue
            if district_ids and db_id not in district_ids:
                continue
            resolved.append({**d, "id": db_id})

        return resolved
