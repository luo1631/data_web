from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, func, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id", ondelete="RESTRICT"))
    address: Mapped[str | None] = mapped_column(String(500))
    building_year: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(50))
    property_fee: Mapped[float | None] = mapped_column(Numeric(10, 2))
    developer: Mapped[str | None] = mapped_column(String(200))
    building_count: Mapped[int | None] = mapped_column(Integer)
    household_count: Mapped[int | None] = mapped_column(Integer)
    green_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    plot_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    lng: Mapped[float | None] = mapped_column(Numeric(10, 7))
    lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("name", "district_id", name="uq_community_name_district"),
        Index("idx_communities_district", "district_id"),
    )
