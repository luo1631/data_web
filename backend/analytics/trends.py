"""
价格趋势分析模块：按月聚合均价、环比/同比、简单移动平均。
"""

from datetime import date, timedelta

from sqlalchemy import func, select, and_, extract, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.price_history import PriceHistory


async def get_price_trends(
    db: AsyncSession, district_id: int | None = None, months: int = 12
) -> dict:
    """价格趋势时间序列。

    优先使用 price_history 表（有历史数据时），
    若无数据则用 listing 表的 listing_date 做近似趋势。

    Args:
        district_id: 限定区县
        months: 回溯月数（默认 12 个月）

    Returns:
        {trends: [{month, avg_unit_price, count}], source: "price_history"|"listings"}
    """
    # 尝试从 price_history 获取
    base = []
    if district_id is not None:
        base.append(Listing.district_id == district_id)

    if base:
        cond = and_(PriceHistory.listing_id == Listing.id, *base)
    else:
        cond = PriceHistory.listing_id == Listing.id

    ph_result = await db.execute(
        select(
            func.strftime("%Y-%m", PriceHistory.record_date).label("month"),
            func.avg(PriceHistory.unit_price).label("avg_price"),
            func.count().label("cnt"),
        ).select_from(PriceHistory).join(Listing, cond)
        .where(PriceHistory.record_date >= date.today() - timedelta(days=months * 32))
        .group_by("month")
        .order_by("month")
    )

    rows = ph_result.all()
    if rows:
        trends = [
            {"month": m, "avg_unit_price": round(float(a), 2), "count": c}
            for m, a, c in rows
        ]
        return _add_mom_yoy(trends, "price_history")

    # 回退：用 listing_date 作为挂牌日期做近似月度均价
    listing_base = [Listing.status == "active"]
    if district_id is not None:
        listing_base.append(Listing.district_id == district_id)

    l_result = await db.execute(
        select(
            func.strftime("%Y-%m", Listing.listing_date).label("month"),
            func.avg(Listing.unit_price).label("avg_price"),
            func.count().label("cnt"),
        ).where(and_(*listing_base), Listing.listing_date.isnot(None))
        .group_by("month")
        .order_by("month")
        .limit(months + 2)
    )

    rows = l_result.all()
    if rows:
        trends = [
            {"month": m, "avg_unit_price": round(float(a), 2), "count": c}
            for m, a, c in rows[-months:]
        ]
        return _add_mom_yoy(trends, "listings")

    return {"trends": [], "source": "none"}


def _add_mom_yoy(trends: list[dict], source: str) -> dict:
    """计算环比 (MoM) 和同比 (YoY)。"""
    for i, t in enumerate(trends):
        # 环比
        if i > 0 and t["count"] > 0 and trends[i - 1]["avg_unit_price"]:
            prev = trends[i - 1]["avg_unit_price"]
            t["mom_pct"] = round((t["avg_unit_price"] - prev) / prev * 100, 2) if prev else None
        else:
            t["mom_pct"] = None

        # 同比 (12 个月前的同月)
        ym = t["month"]
        prev_year_month = f"{int(ym[:4]) - 1}-{ym[5:]}"
        yoy = next((x for x in trends if x["month"] == prev_year_month), None)
        if yoy and yoy["avg_unit_price"]:
            t["yoy_pct"] = round(
                (t["avg_unit_price"] - yoy["avg_unit_price"]) / yoy["avg_unit_price"] * 100, 2
            )
        else:
            t["yoy_pct"] = None

    # 简单移动平均 (SMA-3)
    for i in range(len(trends)):
        window = [t["avg_unit_price"] for t in trends[max(0, i - 2):i + 1] if t["avg_unit_price"]]
        trends[i]["sma_3"] = round(sum(window) / len(window), 2) if window else None

    return {"trends": trends, "source": source}
