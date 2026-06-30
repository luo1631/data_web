"""爬取控制 API 端点：启动/停止/状态查询/SSE 进度流"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.database import async_session as db_session_factory
from app.schemas.crawl import CrawlStartRequest
from app.services.crawl_service import (
    start_crawl,
    stop_crawl,
    get_crawl_progress,
    get_batches,
    generate_sse_events,
)
from app.utils.response import ok, error

router = APIRouter(prefix="/crawl", tags=["crawl"])


@router.post("/start")
async def crawl_start(body: CrawlStartRequest):
    """启动爬取任务。"""
    try:
        result = await start_crawl(db_session_factory, body)
        return ok(data=result.model_dump(), message=result.message)
    except RuntimeError as e:
        return error(code=409, message=str(e))
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/status/{batch_id}")
async def crawl_status(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
):
    """查询爬取批次进度（含各区县任务明细）。"""
    progress = await get_crawl_progress(batch_id, db)
    if not progress:
        return error(code=404, message="批次不存在")
    return ok(data=progress.model_dump())


@router.get("/status/{batch_id}/stream")
async def crawl_status_stream(batch_id: int):
    """SSE 实时进度流 — 每秒推送一次进度。

    用法:
        const es = new EventSource('/api/v1/crawl/status/{batch_id}/stream');
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    return StreamingResponse(
        generate_sse_events(batch_id, db_session_factory),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.post("/stop/{batch_id}")
async def crawl_stop(batch_id: int):
    """停止爬取任务。"""
    result = await stop_crawl(batch_id)
    if result:
        return ok(data={"stopped": True}, message="停止信号已发送")
    return ok(data={"stopped": False}, message="当前无运行中的爬取任务或批次不匹配")


@router.get("/batches")
async def crawl_batches(
    db: AsyncSession = Depends(get_db),
):
    """历史爬取批次列表（最近 20 条）。"""
    batches = await get_batches(db)
    return ok(data=[b.model_dump() for b in batches])
