"""爬取控制 Pydantic 请求/响应 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── 请求体 ──

class CrawlStartRequest(BaseModel):
    """启动爬取请求"""
    type: str = Field("full", description="full | incremental")
    districts: list[int] = Field([], description="指定区县 ID 列表，空=全部")
    max_pages_per_district: int = Field(100, ge=1, le=100, description="每区县最大页数")


# ── 响应体 ──

class CrawlTaskRead(BaseModel):
    """区县爬取任务"""
    id: int
    district_id: int | None = None
    district_name: str | None = None   # JOIN 填充
    status: str = "pending"
    page_start: int = 1
    page_end: int | None = None
    listings_found: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class CrawlBatchRead(BaseModel):
    """爬取批次"""
    id: int
    type: str
    status: str
    total_tasks: int = 0
    completed_tasks: int = 0
    new_listings: int = 0
    updated_listings: int = 0
    removed_listings: int = 0
    error_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tasks: list[CrawlTaskRead] = []    # 关联的任务明细

    model_config = {"from_attributes": True}


class CrawlProgress(BaseModel):
    """SSE 推送的实时进度"""
    batch_id: int
    status: str
    type: str
    total_tasks: int = 0
    completed_tasks: int = 0
    new_listings: int = 0
    updated_listings: int = 0
    tasks: list[CrawlTaskRead] = []


class CrawlStartResponse(BaseModel):
    """启动爬取响应"""
    batch_id: int
    message: str
