"""爬取控制业务逻辑层：启停控制、进度查询、SSE 事件生成"""

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import CrawlBatch, CrawlTask, District
from app.schemas.crawl import (
    CrawlStartRequest, CrawlStartResponse,
    CrawlBatchRead, CrawlTaskRead, CrawlProgress,
)
from crawler.engine import CrawlEngine

logger = logging.getLogger(__name__)

_active_engine: CrawlEngine | None = None
_active_batch_id: int | None = None
_active_task: asyncio.Task | None = None
_crawl_lock = asyncio.Lock()

_CLEANUP_DELAY = 3  # 引擎结束后保留 N 秒让 SSE 读到最终状态


def is_crawling() -> bool:
    return _active_engine is not None and _active_engine.get_progress()["running"]


async def start_crawl(
    session_factory: async_sessionmaker, request: CrawlStartRequest,
) -> CrawlStartResponse:
    global _active_engine, _active_batch_id, _active_task

    async with _crawl_lock:
        if is_crawling():
            raise RuntimeError("已有爬取任务在运行中")

        async with session_factory() as db:
            batch = CrawlBatch(type="full", status="running", total_tasks=1, started_at=datetime.now())
            db.add(batch)
            await db.commit()
            await db.refresh(batch)
            batch_id = batch.id

        engine = CrawlEngine(session_factory)
        _active_engine = engine
        _active_batch_id = batch_id

    async def _run():
        global _active_engine, _active_batch_id, _active_task
        try:
            result = await engine.crawl_all(
                batch_type="full",
                max_pages=request.max_pages_per_district,
                pre_created_batch_id=batch_id,
            )
            logger.info(f"Crawl #{batch_id} done: {result}")
        except asyncio.CancelledError:
            logger.info(f"Crawl #{batch_id} cancelled")
        except Exception:
            logger.error(f"Crawl #{batch_id} failed", exc_info=True)
            # engine 内部已处理 status=failed + DB 落库，这里只记日志

    def _cleanup(_future):
        """任务结束后延迟清除全局引用，留时间给 SSE 读取最终状态。"""
        async def _delayed():
            await asyncio.sleep(_CLEANUP_DELAY)
            global _active_engine, _active_batch_id, _active_task
            _active_engine = None
            _active_batch_id = None
            _active_task = None
            logger.debug(f"Crawl #{batch_id} globals cleaned up")
        asyncio.create_task(_delayed())

    _active_task = asyncio.create_task(_run())
    _active_task.add_done_callback(_cleanup)
    return CrawlStartResponse(batch_id=batch_id, message=f"爬取任务已启动，batch_id={batch_id}")


async def stop_crawl(batch_id: int) -> bool:
    global _active_engine, _active_batch_id, _active_task
    if _active_engine is not None and _active_batch_id == batch_id:
        _active_engine.stop()
        if _active_task is not None:
            _active_task.cancel()
        return True
    from app.database import async_session as _sf
    async with _sf() as db:
        b = await db.get(CrawlBatch, batch_id)
        if b and b.status == "running":
            b.status = "stopped"
            await db.commit()
            return True
    return False


async def get_crawl_progress(batch_id: int, db: AsyncSession) -> CrawlProgress | None:
    """从内存或 DB 获取进度 — 内存优先。"""
    # 如果是活跃引擎，从内存读（实时、精确）
    if _active_engine is not None and _active_batch_id == batch_id:
        p = _active_engine.get_progress()
        engine_status = p.get("status", "running" if p["running"] else "completed")
        if engine_status == "starting":
            engine_status = "running"
        current_district = p.get("current_district", "")
        return CrawlProgress(
            batch_id=batch_id,
            status=engine_status,
            type="full",
            total_tasks=1,
            completed_tasks=0,
            new_listings=p["new"],
            updated_listings=p["updated"],
            current_district=p.get("current_district"),
            tasks=[CrawlTaskRead(
                id=0, status="running" if engine_status == "running" else engine_status,
                page_start=1, page_end=p.get("current_page", 0),
                listings_found=p["new"],
                district_name=current_district or None,
            )],
        )

    # 回退 DB
    batch = await db.get(CrawlBatch, batch_id)
    if not batch:
        return None

    tasks_result = await db.execute(
        select(CrawlTask, District.name).outerjoin(
            District, CrawlTask.district_id == District.id
        ).where(CrawlTask.batch_id == batch_id)
    )
    task_rows = tasks_result.all()
    district_names = [d_name for _, d_name in task_rows if d_name]

    return CrawlProgress(
        batch_id=batch.id,
        status=batch.status or "pending",
        type=batch.type or "full",
        total_tasks=batch.total_tasks or 0,
        completed_tasks=batch.completed_tasks or 0,
        new_listings=batch.new_listings or 0,
        updated_listings=batch.updated_listings or 0,
        current_district=batch.status == "running" and district_names and district_names[-1] or None,
        tasks=[CrawlTaskRead(
            id=t.id,
            district_id=t.district_id,
            district_name=d_name,
            status=t.status or "pending",
            page_start=t.page_start or 1,
            page_end=t.page_end,
            listings_found=t.listings_found or 0,
            error_message=t.error_message,
            started_at=t.started_at, finished_at=t.finished_at,
        ) for t, d_name in task_rows],
    )


async def get_batches(db: AsyncSession) -> list[CrawlBatchRead]:
    result = await db.execute(select(CrawlBatch).order_by(desc(CrawlBatch.id)).limit(20))
    batches = result.scalars().all()
    batch_ids = [b.id for b in batches]

    # 批量加载 tasks + JOIN district 名
    tasks_by_batch: dict[int, list[tuple]] = {b.id: [] for b in batches}
    if batch_ids:
        tr = await db.execute(
            select(CrawlTask, District.name).outerjoin(
                District, CrawlTask.district_id == District.id
            ).where(CrawlTask.batch_id.in_(batch_ids))
        )
        for t, d_name in tr.all():
            tasks_by_batch.setdefault(t.batch_id, []).append((t, d_name))

    output = []
    for batch in batches:
        task_rows = tasks_by_batch.get(batch.id, [])
        output.append(CrawlBatchRead(
            id=batch.id, type=batch.type or "full", status=batch.status or "pending",
            total_tasks=batch.total_tasks or 0,
            completed_tasks=batch.completed_tasks or 0,
            new_listings=batch.new_listings or 0,
            updated_listings=batch.updated_listings or 0,
            removed_listings=batch.removed_listings or 0,
            error_summary=batch.error_summary,
            started_at=batch.started_at, finished_at=batch.finished_at,
            tasks=[CrawlTaskRead(
                id=t.id, district_id=t.district_id,
                district_name=d_name,
                status=t.status or "pending",
                page_start=t.page_start or 1, page_end=t.page_end,
                listings_found=t.listings_found or 0,
                error_message=t.error_message,
                started_at=t.started_at, finished_at=t.finished_at,
            ).model_dump() for t, d_name in task_rows],
        ))
    return output


async def generate_sse_events(batch_id: int, session_factory: async_sessionmaker):
    """SSE — 优先引擎内存，回退 DB，每 2s 推送。

    复用同一个 DB session 避免每秒创建/销毁连接。
    客户端断连时 FastAPI 会取消协程，捕获 CancelledError 退出。
    """
    db = session_factory()
    try:
        while True:
            try:
                progress = await get_crawl_progress(batch_id, db)
                if progress:
                    yield f"data: {json.dumps(progress.model_dump(), ensure_ascii=False, default=str)}\n\n"
                    if progress.status in ("completed", "failed", "stopped"):
                        break
                else:
                    yield f"data: {json.dumps({'error': 'batch not found'})}\n\n"
                    break
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error(f"SSE poll error for batch #{batch_id}", exc_info=True)
                await asyncio.sleep(2)
            await asyncio.sleep(2)
    finally:
        await db.close()
