"""定时爬取任务：每周一凌晨 2:00 执行增量爬取，支持断点恢复。

设计原则:
  - 进程重启后自动恢复未完成的爬取任务
  - crawl_batches 表持久化所有状态（非内存）
  - replace_existing=True 确保重启后不重复注册任务
  - running 状态作为互斥锁，防止重复执行
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, desc, update

from app.database import async_session
from app.models import CrawlBatch, CrawlTask, Listing
from crawler.engine import CrawlEngine

logger = logging.getLogger("scheduler")


# ── 公开入口（供 main.py 的 APScheduler 调用）──

async def run_periodic_update():
    """每 6 小时执行：增量爬取 + 龄期刷新。

    先跑龄期更新（轻量 SQL），再做增量爬取（网络 IO）。
    如果上次增量距今不足 6 小时的批次还在，跳过本次爬取。
    """
    logger.info("[Scheduler] 定时更新任务触发 (6h)")

    # 1. 龄期刷新
    await run_daily_listing_age_update()

    # 2. 增量爬取
    await run_weekly_incremental_crawl()


# ── 公开入口（供 main.py 的 APScheduler 调用）──

async def run_weekly_incremental_crawl():
    """每周增量爬取任务入口。

    执行流程:
      0. 检查是否有用户手动爬取运行中 → 跳过（防止 SQLite 写冲突）
      1. 检查是否有 running 中的增量批次 → 跳过（防止重复）
      2. 如果有 stopped/failed 的未完成批次 → 恢复继续
      3. 否则创建新的增量批次
      4. 运行 CrawlEngine（每个区县 1-2 页，检查新挂牌房源）
    """
    logger.info("[Scheduler] 每周增量爬取任务触发")

    # 0. 与用户触发的全量爬取互斥（共用同一个 SQLite WAL）
    from app.services.crawl_service import is_crawling
    if is_crawling():
        logger.info("[Scheduler] 用户手动爬取运行中，跳过本次增量")
        return {"skipped": True, "reason": "manual crawl in progress"}

    async with async_session() as db:
        # 1. 检查是否有 running 中的增量批次（互斥保护）
        running = await db.execute(
            select(CrawlBatch).where(
                CrawlBatch.type == "incremental",
                CrawlBatch.status == "running",
            ).limit(1)
        )
        existing = running.scalar_one_or_none()
        if existing:
            logger.info(f"[Scheduler] 已有运行中的增量批次 #{existing.id}，跳过")
            return _job_result(existing)

        # 2. 检查是否有可恢复的批次（上次未完成或手动停止）
        resume_batch = await db.execute(
            select(CrawlBatch).where(
                CrawlBatch.type == "incremental",
                CrawlBatch.status.in_(["pending", "stopped"]),
                CrawlBatch.started_at >= datetime.now() - timedelta(days=7),
            ).order_by(desc(CrawlBatch.id)).limit(1)
        )
        resume = resume_batch.scalar_one_or_none()

    # 3. 运行爬虫
    engine = CrawlEngine(async_session)

    try:
        if resume:
            logger.info(f"[Scheduler] 恢复增量批次 #{resume.id}")
            # 标记为 running
            async with async_session() as db2:
                await db2.execute(
                    update(CrawlBatch)
                    .where(CrawlBatch.id == resume.id)
                    .values(status="running")
                )
                await db2.commit()

            result = await engine.crawl_all(
                batch_type="incremental",
                max_pages=2,
                pre_created_batch_id=resume.id,
            )
        else:
            logger.info("[Scheduler] 创建新的增量批次")
            result = await engine.crawl_all(
                batch_type="incremental",
                max_pages=2,
            )

        logger.info(
            f"[Scheduler] 增量爬取完成: "
            f"new={result['new']}, updated={result['updated']}, "
            f"unchanged={result['unchanged']}, errors={result['errors']}"
        )
        return result

    except Exception as e:
        logger.error(f"[Scheduler] 增量爬取异常: {e}", exc_info=True)
        raise


async def run_daily_listing_age_update():
    """每日更新所有活跃房源的 listing_age_days 字段。

    每天凌晨 3:00 执行，使用单次 SQL 批量更新（避免 N+1）。
    """
    logger.info("[Scheduler] listing_age_days 每日更新触发")
    async with async_session() as db:
        # 单次批量 UPDATE: listing_age_days = julianday('now') - julianday(listing_date)
        from sqlalchemy import text
        result = await db.execute(
            text("""
                UPDATE listings
                SET listing_age_days = CAST(julianday('now') - julianday(listing_date) AS INTEGER)
                WHERE status = 'active' AND listing_date IS NOT NULL
            """)
        )
        await db.commit()
        logger.info(f"[Scheduler] listing_age_days 刷新完成: {result.rowcount} 条")


async def resume_incomplete_batches():
    """启动时恢复所有未完成的爬取任务（状态为 running 的标记为 failed）。

    这确保进程重启后，被中断的 batch 不会永久卡在 running 状态。
    """
    logger.info("[Scheduler] 检查未完成的爬取批次...")
    async with async_session() as db:
        result = await db.execute(
            select(CrawlBatch).where(CrawlBatch.status == "running")
        )
        stuck = result.scalars().all()

        for batch in stuck:
            logger.warning(
                f"[Scheduler] 标记未完成的批次 #{batch.id} 为 stopped"
                f"（开始于 {batch.started_at}）"
            )
            await db.execute(
                update(CrawlBatch)
                .where(CrawlBatch.id == batch.id)
                .values(status="stopped")
            )

        if stuck:
            await db.commit()
            logger.info(f"[Scheduler] 已标记 {len(stuck)} 个未完成批次为 stopped")
        else:
            logger.info("[Scheduler] 无未完成的批次")


# ── helpers ──

def _job_result(batch: CrawlBatch) -> dict:
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "new": batch.new_listings or 0,
        "updated": batch.updated_listings or 0,
    }
