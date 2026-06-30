"""
数据库管线：爬虫数据写入 SQLite 的统一入口。

对 SQLite 单写瓶颈的解决方案:
  - 启用 WAL mode（读写不互斥）
  - 设置 busy_timeout=30s（等待而非立即报错）
  - 所有写操作经由 asyncio.Lock 串行化
  - 读操作（SELECT 查重/小区匹配）不受锁限制

用法:
    async with DatabasePipeline(session_factory) as pipeline:
        batch_id = await pipeline.create_crawl_batch("full", 38)
        listing_id, action = await pipeline.upsert_listing(...)
"""

import asyncio
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Listing, Community, CrawlBatch, CrawlTask, PriceHistory


class DatabasePipeline:
    """爬虫数据库操作管线。

    封装所有 crawl_batch/task、listing、community、price_history 的读写操作。
    作为 async context manager 使用，自动管理 session 生命周期。
    """

    def __init__(self, session_factory: async_sessionmaker):
        self._factory = session_factory
        self._write_session: AsyncSession | None = None
        self._write_lock = asyncio.Lock()
        self._batch_id: int | None = None

    # ── context manager ──────────────────────────────

    async def __aenter__(self) -> "DatabasePipeline":
        self._write_session = self._factory()
        # 启用 WAL mode + 设置 busy_timeout
        async with self._write_session.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        return self

    async def __aexit__(self, *args) -> None:
        if self._write_session:
            await self._write_session.close()
            self._write_session = None

    # ── CrawlBatch ───────────────────────────────────

    async def create_crawl_batch(
        self, batch_type: str, total_districts: int
    ) -> int:
        """创建爬取批次记录。

        Args:
            batch_type: "full" 或 "incremental"
            total_districts: 计划爬取的区县数

        Returns:
            新创建的 batch_id
        """
        batch = CrawlBatch(
            type=batch_type,
            status="running",
            total_tasks=total_districts,
            started_at=datetime.now(),
        )
        async with self._write_lock:
            self._write_session.add(batch)
            await self._write_session.commit()
            await self._write_session.refresh(batch)
            self._batch_id = batch.id
            return batch.id

    async def update_crawl_batch(self, batch_id: int, **kwargs) -> None:
        """更新批次统计字段。"""
        async with self._write_lock:
            stmt = (
                update(CrawlBatch)
                .where(CrawlBatch.id == batch_id)
                .values(**kwargs)
            )
            await self._write_session.execute(stmt)
            await self._write_session.commit()

    async def finish_crawl_batch(
        self, batch_id: int, status: str = "completed"
    ) -> None:
        """标记批次完成。"""
        async with self._write_lock:
            stmt = (
                update(CrawlBatch)
                .where(CrawlBatch.id == batch_id)
                .values(status=status, finished_at=datetime.now())
            )
            await self._write_session.execute(stmt)
            await self._write_session.commit()

    # ── CrawlTask ────────────────────────────────────

    async def create_crawl_task(
        self, batch_id: int, district_id: int
    ) -> int:
        """为区县创建爬取任务记录。"""
        task = CrawlTask(
            batch_id=batch_id,
            district_id=district_id,
            status="running",
            started_at=datetime.now(),
        )
        async with self._write_lock:
            self._write_session.add(task)
            await self._write_session.commit()
            await self._write_session.refresh(task)
            return task.id

    async def update_crawl_task(self, task_id: int, **kwargs) -> None:
        """更新任务进度。"""
        async with self._write_lock:
            stmt = (
                update(CrawlTask)
                .where(CrawlTask.id == task_id)
                .values(**kwargs)
            )
            await self._write_session.execute(stmt)
            await self._write_session.commit()

    async def finish_crawl_task(
        self, task_id: int, status: str = "completed", error_message: str | None = None
    ) -> None:
        """标记任务完成（或失败）。"""
        values: dict[str, Any] = {
            "status": status,
            "finished_at": datetime.now(),
        }
        if error_message:
            values["error_message"] = error_message
        await self.update_crawl_task(task_id, **values)

    # ── Listing ──────────────────────────────────────

    async def upsert_listing(
        self,
        data: dict,
        external_id: str,
        district_id: int,
        community_id: int | None,
        md5_hash: str,
        batch_id: int,
        source_url: str,
    ) -> tuple[int, str]:
        """插入或更新房源。

        三种情况:
          - external_id 不存在 → INSERT → ('new')
          - external_id 存在 + MD5 相同 → 更新 last_seen_at → ('unchanged')
          - external_id 存在 + MD5 不同 → 更新全部字段 + 记录价格历史 → ('updated')

        Args:
            data: clean_listing() 返回的 dict
            external_id: 房天下房源 ID
            district_id: 区县 DB ID
            community_id: 小区 DB ID（可为 None）
            md5_hash: 关键字段 MD5
            batch_id: 爬取批次 ID
            source_url: 原始详情页 URL

        Returns:
            (listing_id, action) — action ∈ {'new', 'updated', 'unchanged'}
        """
        existing = await self._get_existing_listing(external_id)

        if existing:
            if not self._is_changed(existing, md5_hash):
                # 无变化：仅更新 last_seen_at
                async with self._write_lock:
                    await self._write_session.execute(
                        update(Listing)
                        .where(Listing.id == existing.id)
                        .values(
                            last_seen_at=func_now(),
                            last_updated_at=func_now(),
                        )
                    )
                    await self._write_session.commit()
                return existing.id, "unchanged"

            # 有变化：记录价格历史 + 更新
            if (
                existing.total_price != data.get("total_price")
                or existing.unit_price != data.get("unit_price")
            ):
                await self._record_price_change(existing, data)

            async with self._write_lock:
                values = _build_listing_values(
                    data, district_id, community_id, md5_hash, batch_id, source_url
                )
                values["last_updated_at"] = func_now()
                values["last_seen_at"] = func_now()
                await self._write_session.execute(
                    update(Listing)
                    .where(Listing.id == existing.id)
                    .values(**values)
                )
                await self._write_session.commit()
            return existing.id, "updated"

        # 全新房源
        listing = Listing(
            external_id=external_id,
            **_build_listing_values(
                data, district_id, community_id, md5_hash, batch_id, source_url
            )
        )
        async with self._write_lock:
            self._write_session.add(listing)
            await self._write_session.commit()
            await self._write_session.refresh(listing)
            return listing.id, "new"

    async def _get_existing_listing(self, external_id: str) -> Listing | None:
        """按 external_id 查找已有房源。"""
        result = await self._write_session.execute(
            select(Listing).where(Listing.external_id == external_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _is_changed(existing: Listing, new_md5: str) -> bool:
        return (existing.md5_hash or "") != new_md5

    async def _record_price_change(
        self, existing: Listing, new_data: dict
    ) -> None:
        """记录价格历史变更。"""
        new_total = new_data.get("total_price")
        new_unit = new_data.get("unit_price")

        if existing.total_price == new_total and existing.unit_price == new_unit:
            return

        async with self._write_lock:
            self._write_session.add(
                PriceHistory(
                    listing_id=existing.id,
                    total_price=existing.total_price,
                    unit_price=existing.unit_price,
                    record_date=date.today(),
                )
            )
            await self._write_session.commit()

    # ── Community ─────────────────────────────────────

    async def upsert_community(
        self, name: str, district_id: int, address: str | None
    ) -> int:
        """查找或创建小区记录。

        Args:
            name: 小区名称
            district_id: 所属区县 ID
            address: 地址（可选）

        Returns:
            community_id
        """
        if not name:
            name = "未知小区"

        async with self._write_lock:
            self._write_session.add(
                Community(name=name, district_id=district_id, address=address)
            )
            await self._write_session.commit()
            # 获取自增 ID
            result = await self._write_session.execute(
                select(Community.id).where(Community.name == name).order_by(
                    Community.id.desc()
                ).limit(1)
            )
            cid = result.scalar_one()
            return cid

    # ── Read helpers (no lock) ───────────────────────

    async def get_communities_in_district(
        self, district_id: int
    ) -> list[tuple[int, str]]:
        """获取某区县所有小区的 (id, name) 列表。"""
        result = await self._write_session.execute(
            select(Community.id, Community.name).where(
                Community.district_id == district_id
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_district_db_id(self, name: str) -> int | None:
        """按区县名称查找数据库 ID。

        先在内存的 DISTRICTS 常量中查找 → 再查数据库。
        """
        from app.models.district import District
        result = await self._write_session.execute(
            select(District.id).where(District.name == name)
        )
        district = result.scalar_one_or_none()
        return district.id if district else None


# ── helpers ──────────────────────────────────────────

def _build_listing_values(
    data: dict,
    district_id: int,
    community_id: int | None,
    md5_hash: str,
    batch_id: int,
    source_url: str,
) -> dict:
    """将清洁数据构建为 Listing 构造参数。"""
    return {
        "district_id": district_id,
        "community_id": community_id,
        "title": data.get("title"),
        "source_platform": "fang.com",
        "source_url": source_url,
        "total_price": data.get("total_price"),
        "unit_price": data.get("unit_price"),
        "area": data.get("area"),
        "room_count": data.get("room_count"),
        "hall_count": data.get("hall_count"),
        "bathroom_count": data.get("bathroom_count"),
        "floor_level": data.get("floor_level"),
        "total_floors": data.get("total_floors"),
        "orientation": data.get("orientation"),
        "decoration": data.get("decoration"),
        "building_type": data.get("building_type"),
        "building_structure": data.get("building_structure"),
        "has_elevator": data.get("has_elevator"),
        "listing_date": data.get("listing_date"),
        "listing_age_days": data.get("listing_age_days"),
        "md5_hash": md5_hash,
        "crawl_batch_id": batch_id,
    }


def func_now():
    """获取当前 UTC 时间，用于 SQLAlchemy 的 server_default 替代。"""
    return datetime.now()
