"""数据完整性测试: FK 约束、唯一约束、MD5 变更检测"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.database import Base


async def _make_session():
    """创建全新内存 SQLite session（含外键约束）"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    from sqlalchemy import event
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


class TestFKIntegrity:
    @pytest.mark.asyncio
    async def test_crawl_batch_cascade_tasks(self):
        from app.models import CrawlBatch, CrawlTask, District
        maker, engine = await _make_session()
        async with maker() as session:
            d = District(name="test_batch", pinyin="t", is_urban=True)
            session.add(d)
            await session.commit()
            await session.refresh(d)

            batch = CrawlBatch(type="full", status="running")
            session.add(batch)
            await session.commit()
            await session.refresh(batch)

            task = CrawlTask(batch_id=batch.id, district_id=d.id, status="running")
            session.add(task)
            await session.commit()

            await session.delete(batch)
            await session.commit()

            result = await session.execute(select(CrawlTask).where(CrawlTask.id == task.id))
            assert result.scalar_one_or_none() is None  # CASCADE deleted
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_listing_district_set_null(self):
        from app.models import District, Listing
        maker, engine = await _make_session()
        async with maker() as session:
            d = District(name="test", pinyin="t", is_urban=True)
            session.add(d)
            await session.commit()
            await session.refresh(d)

            l1 = Listing(external_id="fk_test_1", district_id=d.id, source_platform="test")
            session.add(l1)
            await session.commit()
            await session.refresh(l1)

            await session.delete(d)
            await session.commit()
            await session.refresh(l1)
            assert l1.district_id is None  # SET NULL
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_external_id_unique(self):
        from app.models import Listing
        maker, engine = await _make_session()
        async with maker() as session:
            session.add(Listing(external_id="dup_x", source_platform="test"))
            await session.commit()
            session.add(Listing(external_id="dup_x", source_platform="test"))
            with pytest.raises(Exception):
                await session.commit()
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_status_default(self):
        from app.models import Listing
        maker, engine = await _make_session()
        async with maker() as session:
            l1 = Listing(external_id="status_def", source_platform="test")
            session.add(l1)
            await session.commit()
            await session.refresh(l1)
            assert l1.status == "active"
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_community_unique_name_district(self):
        from app.models import Community, District
        maker, engine = await _make_session()
        async with maker() as session:
            d = District(name="test_comm", pinyin="t", is_urban=True)
            session.add(d)
            await session.commit()
            await session.refresh(d)

            session.add(Community(name="小区A", district_id=d.id))
            await session.commit()
            session.add(Community(name="小区A", district_id=d.id))
            with pytest.raises(Exception):
                await session.commit()
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_counter_defaults_zero(self):
        from app.models import CrawlBatch
        maker, engine = await _make_session()
        async with maker() as session:
            session.add(CrawlBatch(type="full", status="running"))
            await session.commit()
            batch = await session.get(CrawlBatch, 1)
            assert batch.total_tasks == 0
            assert batch.new_listings == 0
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_price_history_cascade(self):
        from datetime import date
        from app.models import Listing, PriceHistory
        maker, engine = await _make_session()
        async with maker() as session:
            l1 = Listing(external_id="ph_cas", source_platform="test")
            session.add(l1)
            await session.commit()
            await session.refresh(l1)
            session.add(PriceHistory(listing_id=l1.id, total_price=100.0, record_date=date.today()))
            await session.commit()
            await session.delete(l1)
            await session.commit()
            result = await session.execute(
                select(PriceHistory).where(PriceHistory.listing_id == l1.id)
            )
            assert result.scalar_one_or_none() is None
        await engine.dispose()


class TestMD5:
    def test_deterministic(self):
        from crawler.dedup import compute_md5
        d = {"total_price": 100, "unit_price": 10000, "area": 80}
        assert compute_md5(d) == compute_md5(d)

    def test_different(self):
        from crawler.dedup import compute_md5
        assert compute_md5({"total_price": 100}) != compute_md5({"total_price": 200})

    def test_bool_differs(self):
        from crawler.dedup import compute_md5
        assert compute_md5({"has_elevator": True}) != compute_md5({"has_elevator": False})
