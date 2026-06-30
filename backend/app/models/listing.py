from datetime import date
from sqlalchemy import String, Integer, SmallInteger, Numeric, Date, DateTime, Boolean, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    title: Mapped[str | None] = mapped_column(String(500))
    source_platform: Mapped[str] = mapped_column(String(100), default="fang.com")
    source_url: Mapped[str | None] = mapped_column(String(1000))

    total_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2))

    area: Mapped[float | None] = mapped_column(Numeric(10, 2))
    room_count: Mapped[int | None] = mapped_column(SmallInteger)
    hall_count: Mapped[int | None] = mapped_column(SmallInteger)
    bathroom_count: Mapped[int | None] = mapped_column(SmallInteger)
    floor_level: Mapped[str | None] = mapped_column(String(20))
    total_floors: Mapped[int | None] = mapped_column(SmallInteger)
    orientation: Mapped[str | None] = mapped_column(String(50))
    decoration: Mapped[str | None] = mapped_column(String(50))
    building_type: Mapped[str | None] = mapped_column(String(50))
    building_structure: Mapped[str | None] = mapped_column(String(50))
    has_elevator: Mapped[bool | None] = mapped_column(Boolean)
    listing_date: Mapped[date | None] = mapped_column(Date)
    listing_age_days: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(20), default="active")
    status_change_date: Mapped[date | None] = mapped_column(Date)

    md5_hash: Mapped[str | None] = mapped_column(String(32))
    crawl_batch_id: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    last_updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # 复合索引（覆盖 99% 查询场景，低区分度字段不建单列索引）
    __table_args__ = (
        Index("idx_listings_status", "status"),
        Index("idx_listings_district_status", "district_id", "status"),
        Index("idx_listings_community_status", "community_id", "status"),
        Index("idx_listings_unit_price", "unit_price"),
        Index("idx_listings_last_updated", "last_updated_at"),
        Index("idx_listings_listing_date", "listing_date"),
    )
