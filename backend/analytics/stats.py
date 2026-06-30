"""
描述性统计分析模块：均价、中位数、分布、区县排名、户型/装修/面积/房龄分布。
"""

import statistics
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.district import District


# ── 价格区间 ──
PRICE_BINS = [
    (None, 50, "50万以下"),
    (50, 100, "50-100万"),
    (100, 150, "100-150万"),
    (150, 200, "150-200万"),
    (200, 300, "200-300万"),
    (300, None, "300万以上"),
]

AREA_BINS = [
    (None, 50, "50㎡以下"),
    (50, 70, "50-70㎡"),
    (70, 90, "70-90㎡"),
    (90, 120, "90-120㎡"),
    (120, 150, "120-150㎡"),
    (150, None, "150㎡以上"),
]

AGE_BINS = [
    (None, 2, "2年以内"),
    (2, 5, "2-5年"),
    (5, 10, "5-10年"),
    (10, 15, "10-15年"),
    (15, 20, "15-20年"),
    (20, None, "20年以上"),
]


async def get_overview_stats(
    db: AsyncSession, district_id: int | None = None
) -> dict:
    """全量概览统计。

    Returns:
        {total, avg_total_price, median_total_price, avg_unit_price,
         median_unit_price, avg_area, price_std, unit_price_std,
         district_ranking: [{name, count, avg_price}],
         price_distribution, area_distribution, age_distribution,
         layout_distribution, decoration_distribution, orientation_distribution}
    """
    base = [Listing.status == "active"]
    if district_id is not None:
        base.append(Listing.district_id == district_id)
    cond = and_(*base)

    # 基础聚合
    agg = await db.execute(
        select(
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.total_price).label("avg_t"),
            func.avg(Listing.unit_price).label("avg_u"),
            func.avg(Listing.area).label("avg_a"),
        ).where(cond)
    )
    row = agg.one()
    total = row.cnt or 0

    # 全量价格数组（用于中位数/标准差）
    prices = await db.execute(
        select(Listing.total_price, Listing.unit_price, Listing.area).where(cond)
    )
    t_vals, u_vals, a_vals = [], [], []
    for tp, up, ar in prices.all():
        if tp is not None: t_vals.append(float(tp))
        if up is not None: u_vals.append(float(up))
        if ar is not None: a_vals.append(float(ar))

    # ── 价格分布 ──
    price_dist = await _bin_count(db, Listing.total_price, PRICE_BINS, base, total)
    area_dist = await _bin_count(db, Listing.area, AREA_BINS, base, total)
    age_dist = await _bin_count(db, Listing.listing_age_days, _days_to_year_bins(AGE_BINS), base, total)

    # ── 户型分布 ──
    layout_rows = await db.execute(
        select(
            Listing.room_count, Listing.hall_count,
            func.count(Listing.id).label("cnt"),
        ).where(cond).group_by(Listing.room_count, Listing.hall_count).order_by(func.count(Listing.id).desc()).limit(10)
    )
    layout_dist = [
        {"label": f"{r}室{h}厅", "count": c, "pct": round(c/total*100, 1) if total else 0}
        for r, h, c in layout_rows.all() if r is not None
    ]

    # ── 装修分布 ──
    deco_dist = await _categorical_dist(db, Listing.decoration, cond, total)

    # ── 朝向分布 ──
    orient_dist = await _categorical_dist(db, Listing.orientation, cond, total)

    # ── 区县排名 ──
    rank_rows = await db.execute(
        select(
            District.name,
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.unit_price).label("avg_u"),
        ).join(Listing, Listing.district_id == District.id).where(cond).group_by(District.name).order_by(func.count(Listing.id).desc())
    )
    district_ranking = [
        {"name": name, "count": c, "avg_unit_price": round(float(au), 2) if au else None}
        for name, c, au in rank_rows.all()
    ]

    return {
        "total_listings": total,
        "avg_total_price": round(float(row.avg_t), 2) if row.avg_t else None,
        "median_total_price": round(statistics.median(t_vals), 2) if t_vals else None,
        "avg_unit_price": round(float(row.avg_u), 2) if row.avg_u else None,
        "median_unit_price": round(statistics.median(u_vals), 2) if u_vals else None,
        "avg_area": round(float(row.avg_a), 2) if row.avg_a else None,
        "median_area": round(statistics.median(a_vals), 2) if a_vals else None,
        "total_price_std": round(statistics.stdev(t_vals), 2) if len(t_vals) > 1 else None,
        "unit_price_std": round(statistics.stdev(u_vals), 2) if len(u_vals) > 1 else None,
        "district_ranking": district_ranking,
        "price_distribution": price_dist,
        "area_distribution": area_dist,
        "age_distribution": age_dist,
        "layout_distribution": layout_dist,
        "decoration_distribution": deco_dist,
        "orientation_distribution": orient_dist,
    }


async def get_district_compare(db: AsyncSession) -> list[dict]:
    """区县对比分析 — 每个区县的均价、中位数、标准差、房源数。"""
    rows = await db.execute(
        select(
            District.name,
            District.is_urban,
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.total_price).label("avg_t"),
            func.avg(Listing.unit_price).label("avg_u"),
        ).join(Listing, Listing.district_id == District.id)
        .where(Listing.status == "active")
        .group_by(District.name)
        .order_by(func.avg(Listing.unit_price).desc())
    )

    result = []
    for name, is_urban, cnt, avg_t, avg_u in rows.all():
        # 每区县中位数单独查
        prices = await db.execute(
            select(Listing.unit_price).where(
                Listing.district_id == District.id,
                District.name == name,
                Listing.status == "active",
            ).join(District)
        )
        vals = [float(p[0]) for p in prices.all() if p[0] is not None]
        result.append({
            "name": name,
            "is_urban": bool(is_urban) if is_urban is not None else True,
            "count": cnt,
            "avg_total_price": round(float(avg_t), 2) if avg_t else None,
            "avg_unit_price": round(float(avg_u), 2) if avg_u else None,
            "median_unit_price": round(statistics.median(vals), 2) if vals else None,
            "std_unit_price": round(statistics.stdev(vals), 2) if len(vals) > 1 else None,
        })

    return result


# ── helpers ──

async def _bin_count(
    db, col, bins: list, base_conds: list, total: int
) -> list[dict]:
    """单次 CASE 查询完成所有分箱计数。"""
    whens = []
    for lo, hi, _ in bins:
        sub = []
        if lo is not None:
            sub.append(col >= lo)
        if hi is not None:
            sub.append(col < hi)
        whens.append(and_(*sub))

    stmt = select(
        *[func.sum(case((w, 1), else_=0)).label(f"b{i}") for i, w in enumerate(whens)]
    ).where(and_(*base_conds))

    counts = (await db.execute(stmt)).one()

    result = []
    for i, (lo, hi, label) in enumerate(bins):
        c = counts[i] or 0
        result.append({
            "range_label": label,
            "count": c,
            "pct": round(c / total * 100, 1) if total > 0 else 0,
        })
    return result


async def _categorical_dist(
    db, col, cond, total: int
) -> list[dict]:
    """分类字段分布。"""
    rows = await db.execute(
        select(col, func.count()).where(cond).group_by(col).order_by(col)
    )
    return [
        {
            "label": v or "未知",
            "count": c,
            "pct": round(c/total*100, 1) if total else 0,
        }
        for v, c in rows.all()
    ]


def _days_to_year_bins(bins):
    """挂牌天数的分箱 → 年分箱近似"""
    out = []
    for lo, hi, label in bins:
        l2 = lo * 365 if lo else None
        h2 = hi * 365 if hi else None
        out.append((l2, h2, label))
    return out
