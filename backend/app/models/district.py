from sqlalchemy import String, Integer, Boolean, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_urban: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_districts_name", "name"),
    )
