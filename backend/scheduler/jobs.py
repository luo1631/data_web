"""定时爬取任务：每周一凌晨 2:00 执行增量爬取，支持断点恢复。

设计原则:
  - 进程重启后自动恢复未完成的爬取任务
  - crawl_batches 表持久化所有状态（非内存）
  - replace_existing=True 确保重启后不重复注册任务
  - running 状态作为互斥锁，防止重复执行
"""

import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass

from sqlalchemy import select, desc, update

from app.database import async_session
from app.models import CrawlBatch, CrawlTask, Listing
from crawler.engine import CrawlEngine

logger = logging.getLogger("scheduler")


# ── 公开入口（供 main.py 的 APScheduler 调用）──

async def run_weekly_incremental_crawl():
    """每周增量爬取任务入口。

    执行流程:
      1. 检查是否有 running 中的增量批次 → 跳过（防止重复）
      2. 如果有 stopped/failed 的未完成批次 → 恢复继续
      3. 否则创建新的增量批次
      4. 运行 CrawlEngine（每个区县 1-2 页，检查新挂牌房源）
    """
    logger.info("[Scheduler] 每周增量爬取任务触发")

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
                district_ids=None,
                batch_type="incremental",
                max_pages=2,  # 增量仅取前 2 页（最新挂牌）
                pre_created_batch_id=resume.id,
            )
        else:
            logger.info("[Scheduler] 创建新的增量批次")
            result = await engine.crawl_all(
                district_ids=None,
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

    每天凌晨 3:00 执行，不需要爬取数据，纯计算字段更新。
    """
    logger.info("[Scheduler] listing_age_days 每日更新触发")
    async with async_session() as db:
        result = await db.execute(
            select(Listing.id, Listing.listing_date).where(
                Listing.status == "active",
                Listing.listing_date.isnot(None),
            )
        )
        updated = 0
        today = date.today()
        for lid, ld in result.all():
            if ld:
                age = (today - ld).days
                await db.execute(
                    update(Listing).where(Listing.id == lid).values(listing_age_days=age)
                )
                updated += 1

        await db.commit()
        logger.info(f"[Scheduler] listing_age_days 刷新完成: {updated} 条")


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
