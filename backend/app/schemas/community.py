"""小区 Pydantic 请求/响应 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


class CommunityRead(BaseModel):
    """小区列表项"""
    id: int
    name: str
    district_id: int | None = None
    address: str | None = None
    building_year: int | None = None
    property_fee: float | None = None
    developer: str | None = None
    building_count: int | None = None
    household_count: int | None = None
    green_rate: float | None = None
    plot_ratio: float | None = None
    lng: float | None = None
    lat: float | None = None
    listing_count: int = 0
    avg_price: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CommunityDetail(CommunityRead):
    """小区详情（含在售房源列表摘要）"""
    min_price: float | None = None
    max_price: float | None = None
    min_area: float | None = None
    max_area: float | None = None
    updated_at: datetime | None = None


class CommunityFilter(BaseModel):
    """小区查询参数"""
    district_id: int | None = Field(None, description="区县 ID")
    keyword: str | None = Field(None, description="小区名搜索")
    page: int = Field(1, ge=1)
    page_size: int = Field(30, ge=1, le=100)
