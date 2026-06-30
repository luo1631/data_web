from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.district import District
from app.models.listing import Listing
from app.schemas.district import DistrictRead, DistrictStats
from app.utils.response import ok

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("")
async def list_districts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(District).order_by(District.id))
    districts = result.scalars().all()

    data = [
        DistrictRead(
            id=d.id,
            name=d.name,
            pinyin=d.pinyin,
            is_urban=bool(d.is_urban),
            listing_count=0,
        )
        for d in districts
    ]
    return ok(data=data)


@router.get("/{district_id}/stats")
async def get_district_stats(district_id: int, db: AsyncSession = Depends(get_db)):
    district = await db.get(District, district_id)
    if not district:
        return ok(data=None)

    result = await db.execute(
        select(
            func.count(Listing.id).label("count"),
            func.avg(Listing.total_price).label("avg_total"),
            func.avg(Listing.unit_price).label("avg_unit"),
        ).where(Listing.district_id == district_id, Listing.status == "active")
    )
    row = result.one()

    return ok(data=DistrictStats(
        id=district.id,
        name=district.name,
        listing_count=row.count or 0,
        avg_total_price=float(row.avg_total) if row.avg_total else None,
        avg_unit_price=float(row.avg_unit) if row.avg_unit else None,
        median_unit_price=None,
    ))
