"""区县 API 端点：列表查询（含房源计数）、区县统计"""

import statistics

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.district import District
from app.models.listing import Listing
from app.schemas.district import DistrictRead, DistrictStats
from app.utils.response import ok, error

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("")
async def list_districts(db: AsyncSession = Depends(get_db)):
    """区县列表 — 附带各区的真实在售房源数。"""
    # 查询所有区县
    result = await db.execute(select(District).order_by(District.id))
    districts = result.scalars().all()

    # 子查询：每个区县的在售房源数
    count_stmt = (
        select(
            Listing.district_id,
            func.count(Listing.id).label("cnt"),
        )
        .where(Listing.status == "active")
        .group_by(Listing.district_id)
    )
    count_result = await db.execute(count_stmt)
    count_map = {row.district_id: row.cnt for row in count_result.all()}

    data = [
        DistrictRead(
            id=d.id,
            name=d.name,
            pinyin=d.pinyin,
            is_urban=bool(d.is_urban),
            listing_count=count_map.get(d.id, 0),
        ).model_dump()
        for d in districts
    ]
    return ok(data=data)


@router.get("/{district_id}/stats")
async def get_district_stats(district_id: int, db: AsyncSession = Depends(get_db)):
    """区县维度统计 — 含真实中位数。"""
    district = await db.get(District, district_id)
    if not district:
        return error(code=404, message="区县不存在")

    base_cond = and_(
        Listing.district_id == district_id,
        Listing.status == "active",
    )

    # 聚合统计
    agg_result = await db.execute(
        select(
            func.count(Listing.id).label("count"),
            func.avg(Listing.total_price).label("avg_total"),
            func.avg(Listing.unit_price).label("avg_unit"),
        ).where(base_cond)
    )
    row = agg_result.one()

    # 中位数计算
    prices_result = await db.execute(
        select(Listing.unit_price).where(base_cond)
    )
    unit_prices = [float(p) for (p,) in prices_result.all() if p is not None]
    median = statistics.median(unit_prices) if unit_prices else None

    return ok(data=DistrictStats(
        id=district.id,
        name=district.name,
        listing_count=row.count or 0,
        avg_total_price=round(float(row.avg_total), 2) if row.avg_total else None,
        avg_unit_price=round(float(row.avg_unit), 2) if row.avg_unit else None,
        median_unit_price=round(median, 2) if median else None,
    ).model_dump())
