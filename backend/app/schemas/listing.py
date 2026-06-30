"""房源 Pydantic 请求/响应 Schema"""

from datetime import date, datetime
from pydantic import BaseModel, Field


# ── 房源列表项（简版）──

class ListingRead(BaseModel):
    id: int
    external_id: str
    title: str | None = None
    district_id: int | None = None
    community_name: str | None = None
    total_price: float | None = None
    unit_price: float | None = None
    area: float | None = None
    room_count: int | None = None
    hall_count: int | None = None
    bathroom_count: int | None = None
    floor_level: str | None = None
    orientation: str | None = None
    decoration: str | None = None
    listing_date: date | None = None
    listing_age_days: int | None = None
    status: str = "active"
    source_url: str | None = None
    first_seen_at: datetime | None = None
    last_updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── 房源详情 ──

class PricePoint(BaseModel):
    """价格历史中的一个数据点"""
    total_price: float | None = None
    unit_price: float | None = None
    record_date: date

    model_config = {"from_attributes": True}


class ListingDetail(ListingRead):
    """比列表更丰富，含价格历史"""
    total_floors: int | None = None
    building_type: str | None = None
    building_structure: str | None = None
    has_elevator: bool | None = None
    community_address: str | None = None
    source_platform: str | None = None
    md5_hash: str | None = None
    last_seen_at: datetime | None = None
    price_history: list[PricePoint] = []


# ── 筛选参数 ──

class ListingFilter(BaseModel):
    """房源列表查询参数 — 全部可选"""
    district_id: int | None = Field(None, description="区县 ID")
    min_price: float | None = Field(None, ge=0, description="最低总价(万)")
    max_price: float | None = Field(None, ge=0, description="最高总价(万)")
    min_area: float | None = Field(None, ge=0, description="最小面积(㎡)")
    max_area: float | None = Field(None, ge=0, description="最大面积(㎡)")
    room_count: int | None = Field(None, ge=1, le=10, description="户型(室)")
    decoration: str | None = Field(None, description="装修情况")
    orientation: str | None = Field(None, description="朝向")
    floor_level: str | None = Field(None, description="楼层")
    status: str | None = Field("active", description="房源状态")
    keyword: str | None = Field(None, description="标题/小区名搜索")
    sort_by: str = Field("last_updated_at", description="排序字段")
    order: str = Field("desc", description="asc / desc")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(30, ge=1, le=100, description="每页条数")


# ── 汇总统计 ──

class PriceRangeInfo(BaseModel):
    """价格段信息"""
    range_label: str           # "50万以下", "50-100万", ...
    count: int
    pct: float                 # 占比(%)


class ListingSummary(BaseModel):
    """房源汇总统计"""
    total_listings: int = 0
    avg_total_price: float | None = None
    median_total_price: float | None = None
    avg_unit_price: float | None = None
    median_unit_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_area: float | None = None
    price_bins: list[PriceRangeInfo] = []
