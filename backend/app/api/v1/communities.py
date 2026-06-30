"""小区 API 端点：列表查询（分页+筛选+搜索）、详情"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.community import Community
from app.models.listing import Listing
from app.schemas.community import CommunityRead, CommunityDetail, CommunityFilter
from app.schemas.common import PaginatedResponse
from app.utils.response import ok, error

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("")
async def list_communities(
    district_id: int | None = Query(None, description="区县 ID"),
    keyword: str | None = Query(None, description="小区名搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """小区列表 — 分页 + 区县筛选 + 关键词搜索。

    每个小区附带在售房源计数和均价。
    """
    conditions = []
    if district_id is not None:
        conditions.append(Community.district_id == district_id)
    if keyword:
        conditions.append(Community.name.ilike(f"%{keyword}%"))

    # 总数
    count_stmt = select(func.count(Community.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询小区
    stmt = select(Community)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(Community.id.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    communities = result.scalars().all()

    # 每个小区附带上在售房源数和均价
    items = []
    for comm in communities:
        stats = await db.execute(
            select(
                func.count(Listing.id).label("cnt"),
                func.avg(Listing.unit_price).label("avg_price"),
            ).where(
                Listing.community_id == comm.id,
                Listing.status == "active",
            )
        )
        row = stats.one()

        items.append(CommunityRead(
            id=comm.id,
            name=comm.name,
            district_id=comm.district_id,
            address=comm.address,
            building_year=comm.building_year,
            property_fee=comm.property_fee,
            developer=comm.developer,
            building_count=comm.building_count,
            household_count=comm.household_count,
            green_rate=comm.green_rate,
            plot_ratio=comm.plot_ratio,
            lng=comm.lng,
            lat=comm.lat,
            listing_count=row.cnt or 0,
            avg_price=round(float(row.avg_price), 2) if row.avg_price else None,
            created_at=comm.created_at,
        ).model_dump())

    total_pages = (total + page_size - 1) // page_size
    return ok(data=PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ).model_dump())


@router.get("/{community_id}")
async def get_community(
    community_id: int,
    db: AsyncSession = Depends(get_db),
):
    """小区详情 — 含在售房源价格/面积范围。"""
    comm = await db.get(Community, community_id)
    if not comm:
        return error(code=404, message="小区不存在")

    # 在售房源统计
    stats = await db.execute(
        select(
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.unit_price).label("avg_price"),
            func.min(Listing.total_price).label("min_price"),
            func.max(Listing.total_price).label("max_price"),
            func.min(Listing.area).label("min_area"),
            func.max(Listing.area).label("max_area"),
        ).where(
            Listing.community_id == community_id,
            Listing.status == "active",
        )
    )
    row = stats.one()

    detail = CommunityDetail(
        id=comm.id,
        name=comm.name,
        district_id=comm.district_id,
        address=comm.address,
        building_year=comm.building_year,
        property_fee=comm.property_fee,
        developer=comm.developer,
        building_count=comm.building_count,
        household_count=comm.household_count,
        green_rate=comm.green_rate,
        plot_ratio=comm.plot_ratio,
        lng=comm.lng,
        lat=comm.lat,
        listing_count=row.cnt or 0,
        avg_price=round(float(row.avg_price), 2) if row.avg_price else None,
        min_price=round(float(row.min_price), 2) if row.min_price else None,
        max_price=round(float(row.max_price), 2) if row.max_price else None,
        min_area=round(float(row.min_area), 2) if row.min_area else None,
        max_area=round(float(row.max_area), 2) if row.max_area else None,
        created_at=comm.created_at,
        updated_at=comm.updated_at,
    )
    return ok(data=detail.model_dump())
