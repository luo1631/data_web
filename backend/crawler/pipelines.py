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
        """标记批次完成，并触发 WAL checkpoint 回收空间。"""
        async with self._write_lock:
            stmt = (
                update(CrawlBatch)
                .where(CrawlBatch.id == batch_id)
                .values(status=status, finished_at=datetime.now())
            )
            await self._write_session.execute(stmt)
            await self._write_session.commit()
            # 批量写入后截断 WAL 文件，防止无限增长
            await self._write_session.execute(
                text("PRAGMA wal_checkpoint(TRUNCATE)")
            )

    # ── CrawlTask ────────────────────────────────────

    async def get_or_create_crawl_task(
        self, batch_id: int, district_id: int
    ) -> int | None:
        """获取或创建区县爬取任务。已完成则返回 None（真断点续爬）。

        先查是否已有完成的 task 对于该 (batch_id, district_id)。
        有 → 跳过，返回 None
        有但未完成 → 返回已有 task_id（复用）
        无 → 创建新 task，返回 task_id
        """
        result = await self._write_session.execute(
            select(CrawlTask).where(
                CrawlTask.batch_id == batch_id,
                CrawlTask.district_id == district_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.status == "completed":
                return None  # 已完成，跳过
            # 未完成 → 复用现有 task
            async with self._write_lock:
                await self._write_session.execute(
                    update(CrawlTask)
                    .where(CrawlTask.id == existing.id)
                    .values(status="running", started_at=datetime.now())
                )
                await self._write_session.commit()
            return existing.id

        # 创建新 task
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

    async def create_crawl_task(
        self, batch_id: int, district_id: int | None
    ) -> int:
        """为区县创建爬取任务记录（始终创建新任务）。"""
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

    # ── Batch commit ──────────────────────────────────

    async def flush(self) -> None:
        """提交当前 session 中所有未提交的写入。

        爬取过程中按页调用，将 60 条房源的写入合并为一次事务，
        消除 per-row commit 的 WAL 争用开销。
        """
        async with self._write_lock:
            await self._write_session.commit()

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
        """插入或更新房源（不提交 — 由页面级 flush() 统一提交）。

        三种情况:
          - external_id 不存在 → INSERT → ('new')
          - external_id 存在 + MD5 相同 → 更新 last_seen_at → ('unchanged')
          - external_id 存在 + MD5 不同 → 更新全部字段 + 记录价格历史 → ('updated')
        """
        existing = await self._get_existing_listing(external_id)

        if existing:
            if not self._is_changed(existing, md5_hash):
                async with self._write_lock:
                    await self._write_session.execute(
                        update(Listing)
                        .where(Listing.id == existing.id)
                        .values(
                            last_seen_at=func_now(),
                            last_updated_at=func_now(),
                        )
                    )
                return existing.id, "unchanged"

            # 有变化：记录价格历史 + 更新（同一个锁范围内完成）
            async with self._write_lock:
                if (
                    existing.total_price != data.get("total_price")
                    or existing.unit_price != data.get("unit_price")
                ):
                    self._write_session.add(
                        PriceHistory(
                            listing_id=existing.id,
                            total_price=existing.total_price,
                            unit_price=existing.unit_price,
                            record_date=date.today(),
                        )
                    )
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
            await self._write_session.flush()       # 获取 autoincrement ID，不提交
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

    # ── Community ─────────────────────────────────────

    async def upsert_community(
        self, name: str, district_id: int, address: str | None,
        lng: float | None = None, lat: float | None = None,
    ) -> int:
        """查找或创建小区记录（不提交 — 由页面级 flush() 统一提交）。"""
        if not name:
            name = "未知小区"

        async with self._write_lock:
            result = await self._write_session.execute(
                select(Community.id).where(
                    Community.name == name,
                    Community.district_id == district_id,
                ).limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                if address or lng is not None:
                    update_vals = {}
                    if address:
                        update_vals["address"] = address
                    if lng is not None:
                        update_vals["lng"] = lng
                    if lat is not None:
                        update_vals["lat"] = lat
                    if update_vals:
                        await self._write_session.execute(
                            update(Community).where(Community.id == existing).values(**update_vals)
                        )
                return existing

            self._write_session.add(
                Community(name=name, district_id=district_id, address=address,
                          lng=lng, lat=lat)
            )
            await self._write_session.flush()       # 获取 autoincrement ID，不提交

            result = await self._write_session.execute(
                select(Community.id).where(
                    Community.name == name,
                    Community.district_id == district_id,
                ).order_by(Community.id.desc()).limit(1)
            )
            return result.scalar_one()

    # ── Remove detection ──────────────────────────

    async def mark_removed_listings(
        self, district_id: int, seen_ids: list[str]
    ) -> int:
        """标记本区县已下架的房源。

        查询本区县 active 房源中不在 seen_ids 里的，
        将其 status 改为 "removed"，记录 status_change_date。

        Returns: 被标记下架的房源数
        """
        if not seen_ids:
            return 0

        today = date.today()
        async with self._write_lock:
            # 找到区县中活跃但本次未出现的房源
            result = await self._write_session.execute(
                select(Listing.external_id).where(
                    Listing.district_id == district_id,
                    Listing.status == "active",
                )
            )
            active_in_db = {row[0] for row in result.all()}
            removed_ids = active_in_db - set(seen_ids)

            if not removed_ids:
                return 0

            # 批量标记为 removed
            stmt = (
                update(Listing)
                .where(
                    Listing.external_id.in_(removed_ids),
                    Listing.district_id == district_id,
                )
                .values(status="removed", status_change_date=today)
            )
            await self._write_session.execute(stmt)
            await self._write_session.commit()
            return len(removed_ids)

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
        """按区县名称查找数据库 ID。"""
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
    """将清洁数据构建为 Listing 构造参数。包含 status='active' 确保重新上架。"""
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
        "status": "active",                     # 使用该字段表示重新上架/持续活跃
        "md5_hash": md5_hash,
        "crawl_batch_id": batch_id,
    }


def func_now():
    """获取当前时间。"""
    return datetime.now()
