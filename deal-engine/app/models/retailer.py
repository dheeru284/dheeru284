from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigIntPK, utcnow


class Retailer(Base):
    __tablename__ = "retailers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)  # adapter registry key
    name: Mapped[str] = mapped_column(String(80))
    domain: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), default="IN")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Health / circuit breaker. status: ok | degraded | unavailable | unconfigured
    status: Mapped[str] = mapped_column(String(20), default="ok")
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    unavailable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
