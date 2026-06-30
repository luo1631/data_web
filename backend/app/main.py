"""
FastAPI 应用入口 — CORS + 路由 + APScheduler 生命周期管理。

APScheduler 是进程内调度器，必须在 FastAPI lifespan 中注册/关闭。
定时任务持久化到 SQLite (crawl_batches)，不受进程重启影响。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.v1.router import api_router

logger = logging.getLogger("app")


# ── APScheduler 初始化 ──

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时注册定时任务 + 恢复中断批次，关闭时清理。"""

    # === 启动时 ===
    from scheduler.jobs import (
        run_weekly_incremental_crawl,
        run_daily_listing_age_update,
        resume_incomplete_batches,
    )

    # 1. 恢复未完成的爬取任务（进程重启后标记 stuck batches）
    await resume_incomplete_batches()

    # 2. 注册定时任务（replace_existing=True 确保重启后覆盖）
    scheduler.add_job(
        func=run_weekly_incremental_crawl,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="weekly_incremental",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        func=run_daily_listing_age_update,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_age_update",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    logger.info("[App] APScheduler 已启动: weekly_incremental (周一 02:00), daily_age_update (每日 03:00)")

    yield  # FastAPI 运行中...

    # === 关闭时 ===
    scheduler.shutdown(wait=False)
    logger.info("[App] APScheduler 已关闭")


# ── FastAPI 实例 ──

app = FastAPI(
    title="重庆二手房数据分析系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
