"""房源 API 端点：列表查询（分页+筛选+排序）、详情、价格历史、汇总统计"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.listing import Listing
from app.models.community import Community
from app.models.price_history import PriceHistory
from app.schemas.common import PaginatedResponse
from app.schemas.listing import (
    ListingFilter,
    ListingRead,
    ListingDetail,
    ListingSummary,
    PricePoint,
)
from app.services.listing_service import (
    build_listing_query,
    get_listing_detail,
    get_listing_summary,
    listing_to_read,
)
from app.utils.response import ok, error

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("")
async def list_listings(
    district_id: int | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_unit_price: float | None = Query(None, ge=0),
    max_unit_price: float | None = Query(None, ge=0),
    min_area: float | None = Query(None, ge=0),
    max_area: float | None = Query(None, ge=0),
    room_count: int | None = Query(None, ge=1, le=10),
    decoration: str | None = Query(None),
    orientation: str | None = Query(None),
    floor_level: str | None = Query(None),
    status: str = Query("active"),
    keyword: str | None = Query(None),
    sort_by: str = Query("last_updated_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """房源列表 — 分页 + 多条件筛选 + 排序。

    支持的筛选维度: district_id、总价/单价区间、面积区间、户型、装修、
    朝向、楼层、状态、关键词搜索。
    """
    filters = ListingFilter(
        district_id=district_id,
        min_price=min_price,
        max_price=max_price,
        min_unit_price=min_unit_price,
        max_unit_price=max_unit_price,
        min_area=min_area,
        max_area=max_area,
        room_count=room_count,
        decoration=decoration,
        orientation=orientation,
        floor_level=floor_level,
        status=status,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )

    # 构建查询
    stmt = build_listing_query(filters)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    listings = result.scalars().all()

    # 批量获取小区名
    comm_ids = {l.community_id for l in listings if l.community_id}
    comm_map: dict[int, str] = {}
    if comm_ids:
        comm_result = await db.execute(
            select(Community.id, Community.name).where(
                Community.id.in_(comm_ids)
            )
        )
        comm_map = {cid: cname for cid, cname in comm_result.all()}

    items = [
        listing_to_read(l, community_name=comm_map.get(l.community_id))
        for l in listings
    ]

    total_pages = (total + page_size - 1) // page_size
    return ok(data=PaginatedResponse(
        items=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ).model_dump())


@router.get("/stats/summary")
async def listings_summary(
    district_id: int | None = Query(None, description="区县 ID — 不传则全市"),
    db: AsyncSession = Depends(get_db),
):
    """房源汇总统计 — 均价、中位数、价格段分布等。"""
    summary = await get_listing_summary(db, district_id=district_id)
    return ok(data=summary.model_dump())


@router.get("/{listing_id}")
async def get_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    """房源详情 — 含价格历史。"""
    detail = await get_listing_detail(db, listing_id)
    if not detail:
        return error(code=404, message="房源不存在")
    return ok(data=detail.model_dump())


@router.get("/{listing_id}/history")
async def get_listing_price_history(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    """房源价格变动历史。"""
    listing = await db.get(Listing, listing_id)
    if not listing:
        return error(code=404, message="房源不存在")

    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.listing_id == listing_id)
        .order_by(PriceHistory.record_date.desc())
    )
    history = result.scalars().all()

    data = [
        PricePoint(
            total_price=h.total_price,
            unit_price=h.unit_price,
            record_date=h.record_date,
        ).model_dump()
        for h in history
    ]
    return ok(data=data)
