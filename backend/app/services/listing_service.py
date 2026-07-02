"""房源业务逻辑层：查询构建、聚合统计、详情组装"""

import statistics
from typing import Sequence

from sqlalchemy import Select, func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.price_history import PriceHistory
from app.models.community import Community
from app.schemas.listing import (
    ListingFilter,
    ListingRead,
    ListingDetail,
    ListingSummary,
    PriceRangeInfo,
    PricePoint,
)

# 合法的排序字段白名单（防 SQL 注入）
SORTABLE_FIELDS = {
    "id", "total_price", "unit_price", "area", "room_count",
    "listing_date", "first_seen_at", "last_updated_at", "listing_age_days",
}

PRICE_BINS = [
    (None, 50, "50万以下"),
    (50, 100, "50-100万"),
    (100, 150, "100-150万"),
    (150, 200, "150-200万"),
    (200, 300, "200-300万"),
    (300, None, "300万以上"),
]


def build_listing_query(filters: ListingFilter) -> Select:
    """根据筛选条件构建 Listing 查询（不含分页）。

    Args:
        filters: 前端传来的筛选参数

    Returns:
        SQLAlchemy Select 对象，可追加 limit/offset
    """
    stmt = select(Listing)

    # 筛选条件
    conditions = []

    if filters.district_id is not None:
        conditions.append(Listing.district_id == filters.district_id)

    if filters.min_price is not None:
        conditions.append(Listing.total_price >= filters.min_price)

    if filters.max_price is not None:
        conditions.append(Listing.total_price <= filters.max_price)

    if filters.min_unit_price is not None:
        conditions.append(Listing.unit_price >= filters.min_unit_price)

    if filters.max_unit_price is not None:
        conditions.append(Listing.unit_price <= filters.max_unit_price)

    if filters.min_area is not None:
        conditions.append(Listing.area >= filters.min_area)

    if filters.max_area is not None:
        conditions.append(Listing.area <= filters.max_area)

    if filters.room_count is not None:
        conditions.append(Listing.room_count == filters.room_count)

    if filters.decoration:
        conditions.append(Listing.decoration == filters.decoration)

    if filters.orientation:
        conditions.append(Listing.orientation == filters.orientation)

    if filters.floor_level:
        conditions.append(Listing.floor_level == filters.floor_level)

    if filters.listing_type is not None:
        conditions.append(Listing.listing_type == filters.listing_type)

    if filters.status is not None:
        conditions.append(Listing.status == filters.status)

    if filters.keyword:
        kw = f"%{filters.keyword}%"
        conditions.append(
            (Listing.title.ilike(kw)) |
            (Listing.external_id.ilike(kw))
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # 排序（白名单校验）
    sort_field = filters.sort_by if filters.sort_by in SORTABLE_FIELDS else "last_updated_at"
    col = getattr(Listing, sort_field)
    if filters.order == "asc":
        stmt = stmt.order_by(col.asc())
    else:
        stmt = stmt.order_by(col.desc())

    return stmt


async def get_listing_detail(
    db: AsyncSession, listing_id: int
) -> ListingDetail | None:
    """获取房源详情（含价格历史 + 小区名）。

    Args:
        db: 数据库 session
        listing_id: 房源数据库主键 ID

    Returns:
        ListingDetail, 不存在返回 None
    """
    listing = await db.get(Listing, listing_id)
    if not listing:
        return None

    # 查询价格历史
    history_result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.listing_id == listing_id)
        .order_by(PriceHistory.record_date.desc())
    )
    history = history_result.scalars().all()

    # 查询小区名
    community_name = None
    community_address = None
    if listing.community_id:
        comm = await db.get(Community, listing.community_id)
        if comm:
            community_name = comm.name
            community_address = comm.address

    return ListingDetail(
        id=listing.id,
        external_id=listing.external_id,
        title=listing.title,
        district_id=listing.district_id,
        community_name=community_name,
        listing_type=listing.listing_type or "regular",
        total_price=listing.total_price,
        unit_price=listing.unit_price,
        area=listing.area,
        room_count=listing.room_count,
        hall_count=listing.hall_count,
        bathroom_count=listing.bathroom_count,
        floor_level=listing.floor_level,
        total_floors=listing.total_floors,
        orientation=listing.orientation,
        decoration=listing.decoration,
        building_type=listing.building_type,
        building_structure=listing.building_structure,
        has_elevator=listing.has_elevator,
        listing_date=listing.listing_date,
        listing_age_days=listing.listing_age_days,
        status=listing.status or "active",
        source_url=listing.source_url,
        source_platform=listing.source_platform,
        md5_hash=listing.md5_hash,
        community_address=community_address,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        last_updated_at=listing.last_updated_at,
        price_history=[
            PricePoint(
                total_price=h.total_price,
                unit_price=h.unit_price,
                record_date=h.record_date,
            )
            for h in history
        ],
    )


async def get_listing_summary(
    db: AsyncSession, district_id: int | None = None
) -> ListingSummary:
    """获取房源汇总统计。

    Args:
        db: 数据库 session
        district_id: 可选，限定区县

    Returns:
        ListingSummary 含 count、avg、median、min/max、价格段分布
    """
    # 基础条件
    base_cond = [Listing.status == "active"]
    if district_id is not None:
        base_cond.append(Listing.district_id == district_id)

    # 聚合查询
    agg_result = await db.execute(
        select(
            func.count(Listing.id).label("cnt"),
            func.avg(Listing.total_price).label("avg_total"),
            func.avg(Listing.unit_price).label("avg_unit"),
            func.avg(Listing.area).label("avg_area"),
            func.min(Listing.total_price).label("min_price"),
            func.max(Listing.total_price).label("max_price"),
        ).where(and_(*base_cond))
    )
    row = agg_result.one()

    total = row.cnt or 0

    # 中位数计算：取所有活跃房源的 unit_price 和 total_price
    prices = await db.execute(
        select(Listing.total_price, Listing.unit_price).where(and_(*base_cond))
    )
    total_prices = []
    unit_prices = []
    for tp, up in prices.all():
        if tp is not None:
            total_prices.append(float(tp))
        if up is not None:
            unit_prices.append(float(up))

    median_total = statistics.median(total_prices) if total_prices else None
    median_unit = statistics.median(unit_prices) if unit_prices else None

    # 价格段分布（单次 CASE WHEN 查询，替代 6 次独立 COUNT）
    from sqlalchemy import case
    bin_whens = []
    bin_labels = []
    for lo, hi, label in PRICE_BINS:
        sub_conds = []
        if lo is not None:
            sub_conds.append(Listing.total_price >= lo)
        if hi is not None:
            sub_conds.append(Listing.total_price < hi)
        bin_whens.append(and_(*sub_conds))
        bin_labels.append(label)

    bin_selects = [
        func.sum(case((w, 1), else_=0)).label(f"b{i}")
        for i, w in enumerate(bin_whens)
    ]
    bin_result = await db.execute(
        select(*bin_selects).where(and_(*base_cond))
    )
    bin_counts = bin_result.one()

    bins = [
        PriceRangeInfo(
            range_label=label,
            count=bin_counts[i] or 0,
            pct=round((bin_counts[i] or 0) / total * 100, 1) if total > 0 else 0.0,
        )
        for i, label in enumerate(bin_labels)
    ]

    return ListingSummary(
        total_listings=total,
        avg_total_price=round(float(row.avg_total), 2) if row.avg_total else None,
        median_total_price=round(median_total, 2) if median_total else None,
        avg_unit_price=round(float(row.avg_unit), 2) if row.avg_unit else None,
        median_unit_price=round(median_unit, 2) if median_unit else None,
        min_price=round(float(row.min_price), 2) if row.min_price else None,
        max_price=round(float(row.max_price), 2) if row.max_price else None,
        avg_area=round(float(row.avg_area), 2) if row.avg_area else None,
        price_bins=bins,
    )


def listing_to_read(listing: Listing, community_name: str | None = None) -> ListingRead:
    """ORM → 列表项 Schema，可注入 JOIN 得到的小区名。

    Args:
        listing: ORM 对象
        community_name: 可选，从 JOIN 查询得到的小区名

    Returns:
        ListingRead
    """
    return ListingRead(
        id=listing.id,
        external_id=listing.external_id,
        title=listing.title,
        district_id=listing.district_id,
        community_name=community_name,
        listing_type=listing.listing_type or "regular",
        total_price=listing.total_price,
        unit_price=listing.unit_price,
        area=listing.area,
        room_count=listing.room_count,
        hall_count=listing.hall_count,
        bathroom_count=listing.bathroom_count,
        floor_level=listing.floor_level,
        orientation=listing.orientation,
        decoration=listing.decoration,
        listing_date=listing.listing_date,
        listing_age_days=listing.listing_age_days,
        status=listing.status or "active",
        source_url=listing.source_url,
        first_seen_at=listing.first_seen_at,
        last_updated_at=listing.last_updated_at,
    )
