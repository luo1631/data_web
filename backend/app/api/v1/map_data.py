"""地图数据 API — 返回各区县均价用于地图着色"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.listing import Listing
from app.models.district import District
from app.utils.response import ok, error

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/district-prices")
async def district_prices(db: AsyncSession = Depends(get_db)):
    """返回各区县均价数据，用于 ECharts 地图着色。

    响应:
        [
          {"name": "渝北区", "value": 14865},
          {"name": "江北区", "value": 16200},
          ...
        ]

    数据按 value 降序排列。
    """
    try:
        result = await db.execute(
            select(
                District.name,
                func.avg(Listing.unit_price).label("avg_price"),
                func.count(Listing.id).label("cnt"),
            )
            .join(Listing, Listing.district_id == District.id)
            .where(Listing.status == "active", Listing.unit_price.isnot(None))
            .group_by(District.name)
            .order_by(func.avg(Listing.unit_price).desc())
        )

        data = [
            {
                "name": name,
                "value": round(float(avg_price), 2) if avg_price else 0,
                "count": cnt,
            }
            for name, avg_price, cnt in result.all()
        ]

        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))


@router.get("/district-heatmap")
async def district_heatmap(db: AsyncSession = Depends(get_db)):
    """返回各区县房源密度热力图数据（用于散点图叠加）。

    从 communities 表的 lng/lat 获取坐标，聚合每个区县的房源数量。
    """
    try:
        from app.models.community import Community

        result = await db.execute(
            select(
                District.name,
                func.avg(Community.lng).label("lng"),
                func.avg(Community.lat).label("lat"),
                func.count(Listing.id).label("cnt"),
            )
            .select_from(District)
            .join(Listing, Listing.district_id == District.id)
            .outerjoin(Community, Community.id == Listing.community_id)
            .where(Listing.status == "active")
            .group_by(District.name)
        )

        data = [
            {
                "name": name,
                "lng": round(float(lng), 4) if lng else None,
                "lat": round(float(lat), 4) if lat else None,
                "value": cnt,
            }
            for name, lng, lat, cnt in result.all()
            if lng is not None
        ]

        return ok(data=data)
    except Exception as e:
        return error(code=500, message=str(e))
