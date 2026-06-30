"""Pytest fixtures: 创建内存 SQLite 测试数据库。"""

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import (
    District,
    Community,
    Listing,
    PriceHistory,
    CrawlBatch,
    CrawlTask,
)


@pytest.fixture(scope="session")
def event_loop():
    """为 session-scoped async fixture 创建事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """创建内存 SQLite 测试数据库 + session。

    每个测试函数独立创建/销毁数据库。
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()
