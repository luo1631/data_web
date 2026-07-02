"""
FastAPI 应用入口 — CORS + 路由 + 定时增量更新。

服务运行期间每 6 小时自动执行增量爬取 + 龄期刷新，
无需依赖系统计划任务或服务常驻。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api.v1.router import api_router

logger = logging.getLogger("app")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时恢复未完成批次 + 注册定时任务，关闭时清理调度器。"""

    from scheduler.jobs import (
        run_periodic_update,
        resume_incomplete_batches,
    )
    from analytics.trends import setup_trends_scheduler
    from app.database import async_session

    # 确保索引存在（对已有表不会重复创建，仅补充缺失的）
    from app.config import settings as _cfg
    import sqlite3
    _db_path = _cfg.database_url.replace("sqlite+aiosqlite:///", "")
    _conn = sqlite3.connect(f"file:{_db_path}?mode=rwc", uri=True)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_batches_status ON crawl_batches(status)")
    _conn.close()

    await resume_incomplete_batches()

    scheduler.add_job(
        func=run_periodic_update,
        trigger=IntervalTrigger(hours=6),
        id="periodic_update",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("[App] 爬虫定时任务已启动: 每 6h 增量爬取 + 趋势刷新")

    # 趋势计算: 每日 6:00 + 启动补算
    setup_trends_scheduler(scheduler)
    logger.info("[App] 趋势定时任务已注册")

    yield

    scheduler.shutdown(wait=False)
    logger.info("[App] 定时任务已关闭")


app = FastAPI(
    title="重庆二手房数据分析系统",
    version="0.2.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
