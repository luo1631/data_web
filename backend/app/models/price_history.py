from datetime import date
from sqlalchemy import String, Integer, Numeric, Date, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    total_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_price_history_listing", "listing_id"),
        Index("idx_price_history_date", "record_date"),
    )
