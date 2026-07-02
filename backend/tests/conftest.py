"""Pytest fixtures: 内存 SQLite 测试数据库 + FastAPI 测试客户端"""

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


def pytest_configure(config):
    """注册自定义 warning filter 和 markers。"""
    config.addinivalue_line(
        "filterwarnings",
        "ignore:Please use `import python_multipart` instead:PendingDeprecationWarning",
    )
    config.addinivalue_line(
        "markers",
        "network: tests that require internet access to fang.com"
    )


@pytest.fixture(scope="function")
async def db_session():
    """每个测试函数独立创建/销毁内存 SQLite 数据库。"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session() as session:
        yield session

    await engine.dispose()
