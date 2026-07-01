"""
描述性统计分析模块：均价、中位数、分布、区县排名、户型/装修/面积/房龄分布。

含简单 TTL 内存缓存（60s），LRU 淘汰，避免高频请求重复聚合计算。
"""

import statistics
import time
from collections import OrderedDict
from typing import Sequence

from sqlalchemy import func, select, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

# ── LRU TTL 缓存（无外部依赖）──
_OVERVIEW_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_COMPARE_CACHE: list = [0, []]  # [timestamp, data] 可变列表引用
_CACHE_TTL = 60  # 秒
_CACHE_MAX_SIZE = 50


def _evict_lru(cache: OrderedDict, max_size: int) -> None:
    """LRU 淘汰：超出 max_size 时移除最旧条目。"""
    while len(cache) > max_size:
        cache.popitem(last=False)


async def get_overview_stats(
    db: AsyncSession, district_id: int | None = None
) -> dict:
    """全量概览统计（60s TTL 缓存，LRU 淘汰）。"""
    cache_key = f"overview_{district_id}"
    now = time.time()
    cached = _OVERVIEW_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    result = await _compute_overview_stats(db, district_id)
    # LRU: 先删旧 key 再插入（更新位置）
    _OVERVIEW_CACHE.pop(cache_key, None)
    _OVERVIEW_CACHE[cache_key] = (now, result)
    _evict_lru(_OVERVIEW_CACHE, _CACHE_MAX_SIZE)
    return result


async def get_district_compare(db: AsyncSession) -> list[dict]:
    """区县对比分析（60s TTL 缓存）。"""
    now = time.time()
    if _COMPARE_CACHE[0] and (now - _COMPARE_CACHE[0]) < _CACHE_TTL:
        return _COMPARE_CACHE[1]

    result = await _compute_district_compare(db)
    _COMPARE_CACHE[0] = now
    _COMPARE_CACHE[1] = result
    return result


# ── 内部实现（无缓存）──

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


async def _compute_overview_stats(
    db: AsyncSession, district_id: int | None = None
) -> dict:
    """全量概览统计（内部实现，无缓存）。"""
    base = [Listing.status == "active"]
    if district_id is not None:
        base.append(Listing.district_id == district_id)
    cond = and_(*base)

    # 基础聚合（过滤空值和零值脏数据）
    agg = await db.execute(
        select(
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.total_price).filter(Listing.total_price > 0).label("avg_t"),
            func.avg(Listing.unit_price).filter(Listing.unit_price > 0).label("avg_u"),
            func.avg(Listing.area).filter(Listing.area > 0).label("avg_a"),
            func.count(Listing.id).filter(Listing.unit_price.isnot(None), Listing.unit_price > 0).label("valid_u"),
            func.count(Listing.id).filter(Listing.total_price.isnot(None), Listing.total_price > 0).label("valid_t"),
        ).where(cond)
    )
    row = agg.one()
    total = row.cnt or 0

    # 全量价格数组（用于中位数/标准差），排除 None 和 ≤0
    prices = await db.execute(
        select(Listing.total_price, Listing.unit_price, Listing.area).where(cond)
    )
    t_vals, u_vals, a_vals = [], [], []
    for tp, up, ar in prices.all():
        if tp is not None and tp > 0: t_vals.append(float(tp))
        if up is not None and up > 0: u_vals.append(float(up))
        if ar is not None and ar > 0: a_vals.append(float(ar))

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

    # ── 城市/郊区分组统计 ──
    urban_suburb_rows = await db.execute(
        select(
            District.is_urban,
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.unit_price).filter(Listing.unit_price > 0).label("avg_u"),
        ).join(Listing, Listing.district_id == District.id)
        .where(cond, District.is_urban.isnot(None))
        .group_by(District.is_urban)
    )
    urban_cnt, urban_avg = 0, None
    suburb_cnt, suburb_avg = 0, None
    for is_u, cnt, au in urban_suburb_rows.all():
        if is_u:
            urban_cnt = cnt
            urban_avg = round(float(au), 2) if au else None
        else:
            suburb_cnt = cnt
            suburb_avg = round(float(au), 2) if au else None

    # ── 区县排名（过滤零值脏数据）──
    rank_rows = await db.execute(
        select(
            District.name,
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.unit_price).filter(Listing.unit_price > 0).label("avg_u"),
        ).join(Listing, Listing.district_id == District.id).where(cond).group_by(District.name).order_by(func.count(Listing.id).desc())
    )
    district_ranking = [
        {"name": name, "count": c, "avg_unit_price": round(float(au), 2) if au else None}
        for name, c, au in rank_rows.all()
    ]

    return {
        "total_listings": total,
        "valid_price_count": row.valid_u or 0,
        "valid_total_count": row.valid_t or 0,
        "avg_total_price": round(float(row.avg_t), 2) if row.avg_t else None,
        "median_total_price": round(statistics.median(t_vals), 2) if t_vals else None,
        "avg_unit_price": round(float(row.avg_u), 2) if row.avg_u else None,
        "median_unit_price": round(statistics.median(u_vals), 2) if u_vals else None,
        "avg_area": round(float(row.avg_a), 2) if row.avg_a else None,
        "median_area": round(statistics.median(a_vals), 2) if a_vals else None,
        "total_price_std": round(statistics.stdev(t_vals), 2) if len(t_vals) > 1 else None,
        "unit_price_std": round(statistics.stdev(u_vals), 2) if len(u_vals) > 1 else None,
        # 城市/郊区分组
        "urban_count": urban_cnt,
        "urban_avg_unit_price": urban_avg,
        "suburb_count": suburb_cnt,
        "suburb_avg_unit_price": suburb_avg,
        "district_ranking": district_ranking,
        "price_distribution": price_dist,
        "area_distribution": area_dist,
        "age_distribution": age_dist,
        "layout_distribution": layout_dist,
        "decoration_distribution": deco_dist,
        "orientation_distribution": orient_dist,
    }


async def _compute_district_compare(db: AsyncSession) -> list[dict]:
    """区县对比分析 — 每个区县的均价、中位数、标准差、房源数。（内部实现）

    优化: 一次查询获取所有 (district_name, unit_price) 对，Python 侧分组计算
          中位数和标准差，避免 N+1 查询。
    """
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

    # 一次查询获取所有区县的 unit_price 对
    all_prices = await db.execute(
        select(District.name, Listing.unit_price)
        .join(Listing, Listing.district_id == District.id)
        .where(Listing.status == "active", Listing.unit_price.isnot(None))
    )
    price_map: dict[str, list[float]] = {}
    for name, up in all_prices.all():
        if up is not None:
            price_map.setdefault(name, []).append(float(up))

    result = []
    for name, is_urban, cnt, avg_t, avg_u in rows.all():
        vals = price_map.get(name, [])
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
