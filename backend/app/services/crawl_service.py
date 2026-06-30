"""爬取控制业务逻辑层：启停控制、进度查询、SSE 事件生成"""

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import CrawlBatch, CrawlTask, District
from app.schemas.crawl import (
    CrawlStartRequest,
    CrawlStartResponse,
    CrawlBatchRead,
    CrawlTaskRead,
    CrawlProgress,
)
from crawler.engine import CrawlEngine

logger = logging.getLogger(__name__)

# 模块级：当前活跃的爬虫引擎实例
_active_engine: CrawlEngine | None = None
_crawl_lock = asyncio.Lock()


def is_crawling() -> bool:
    """是否有正在运行的爬虫"""
    return _active_engine is not None and _active_engine.get_progress()["running"]


async def start_crawl(
    session_factory: async_sessionmaker,
    request: CrawlStartRequest,
) -> CrawlStartResponse:
    """启动爬取任务（异步，在 BackgroundTasks 中运行）。

    Args:
        session_factory: 数据库 session 工厂
        request: 启动参数

    Returns:
        新创建的 batch_id

    Raises:
        RuntimeError: 已有爬虫在运行
    """
    global _active_engine

    async with _crawl_lock:
        if is_crawling():
            raise RuntimeError("已有爬取任务在运行中，请先停止后再启动")

        engine = CrawlEngine(session_factory)
        _active_engine = engine

    # 异步启动爬虫（不 await，在后台运行）
    async def _run():
        try:
            await engine.crawl_all(
                district_ids=request.districts if request.districts else None,
                batch_type=request.type,
                max_pages=request.max_pages_per_district,
            )
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
        finally:
            global _active_engine
            _active_engine = None

    asyncio.create_task(_run())

    # 短暂等待让 batch 创建完成
    await asyncio.sleep(0.5)

    # 查询最新 batch_id
    async with session_factory() as db:
        result = await db.execute(
            select(CrawlBatch.id).order_by(desc(CrawlBatch.id)).limit(1)
        )
        batch_id = result.scalar_one_or_none()
        if not batch_id:
            raise RuntimeError("Failed to create crawl batch")

    return CrawlStartResponse(
        batch_id=batch_id,
        message=f"爬取任务已启动，batch_id={batch_id}",
    )


async def stop_crawl(batch_id: int) -> bool:
    """停止爬取任务。

    Args:
        batch_id: 要停止的批次 ID

    Returns:
        是否成功发送停止信号
    """
    global _active_engine
    if _active_engine is None:
        return False
    _active_engine.stop()
    return True


async def get_crawl_progress(
    batch_id: int, db: AsyncSession
) -> CrawlProgress | None:
    """从数据库查询爬取进度。

    Args:
        batch_id: 批次 ID
        db: 数据库 session

    Returns:
        进度快照，批次不存在返回 None
    """
    batch = await db.get(CrawlBatch, batch_id)
    if not batch:
        return None

    # 查询关联的区县任务
    tasks_result = await db.execute(
        select(CrawlTask).where(CrawlTask.batch_id == batch_id)
    )
    tasks = tasks_result.scalars().all()

    # JOIN 区县名称
    task_list = []
    for t in tasks:
        district_name = None
        if t.district_id:
            d = await db.get(District, t.district_id)
            district_name = d.name if d else None
        task_list.append(CrawlTaskRead(
            id=t.id,
            district_id=t.district_id,
            district_name=district_name,
            status=t.status or "pending",
            page_start=t.page_start or 1,
            page_end=t.page_end,
            listings_found=t.listings_found or 0,
            error_message=t.error_message,
            started_at=t.started_at,
            finished_at=t.finished_at,
        ))

    return CrawlProgress(
        batch_id=batch.id,
        status=batch.status or "pending",
        type=batch.type or "full",
        total_tasks=batch.total_tasks or 0,
        completed_tasks=batch.completed_tasks or 0,
        new_listings=batch.new_listings or 0,
        updated_listings=batch.updated_listings or 0,
        tasks=task_list,
    )


async def get_batches(db: AsyncSession) -> list[CrawlBatchRead]:
    """查询最近的爬取批次列表（最近 20 条）。

    Args:
        db: 数据库 session

    Returns:
        批次列表
    """
    result = await db.execute(
        select(CrawlBatch).order_by(desc(CrawlBatch.id)).limit(20)
    )
    batches = result.scalars().all()

    output = []
    for batch in batches:
        # 查询每个批次的区县任务
        tasks_result = await db.execute(
            select(CrawlTask).where(CrawlTask.batch_id == batch.id)
        )
        tasks = tasks_result.scalars().all()

        task_list = []
        for t in tasks:
            district_name = None
            if t.district_id:
                d = await db.get(District, t.district_id)
                district_name = d.name if d else None
            task_list.append(CrawlTaskRead(
                id=t.id,
                district_id=t.district_id,
                district_name=district_name,
                status=t.status or "pending",
                page_start=t.page_start or 1,
                page_end=t.page_end,
                listings_found=t.listings_found or 0,
                error_message=t.error_message,
                started_at=t.started_at,
                finished_at=t.finished_at,
            ))

        output.append(CrawlBatchRead(
            id=batch.id,
            type=batch.type or "full",
            status=batch.status or "pending",
            total_tasks=batch.total_tasks or 0,
            completed_tasks=batch.completed_tasks or 0,
            new_listings=batch.new_listings or 0,
            updated_listings=batch.updated_listings or 0,
            removed_listings=batch.removed_listings or 0,
            error_summary=batch.error_summary,
            started_at=batch.started_at,
            finished_at=batch.finished_at,
            tasks=[t.model_dump() for t in task_list],
        ))

    return output


async def generate_sse_events(
    batch_id: int, session_factory: async_sessionmaker
):
    """SSE 事件流生成器 — 每秒查询一次数据库并推送进度。

    Args:
        batch_id: 要监听的批次 ID
        session_factory: 数据库 session 工厂

    Yields:
        SSE 格式的字符串
    """
    while True:
        try:
            async with session_factory() as db:
                progress = await get_crawl_progress(batch_id, db)
                if progress:
                    data = json.dumps(progress.model_dump(), ensure_ascii=False, default=str)
                    yield f"data: {data}\n\n"

                    # 爬取完成 → 停止推送
                    if progress.status in ("completed", "failed"):
                        break
                else:
                    # 批次不存在
                    yield f"data: {json.dumps({'error': 'batch not found'})}\n\n"
                    break

        except Exception as e:
            logger.error(f"SSE error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break

        await asyncio.sleep(1)
