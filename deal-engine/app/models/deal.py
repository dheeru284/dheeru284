from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigIntPK, JSONType, utcnow


class DealEvent(Base):
    __tablename__ = "deal_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_price: Mapped[float] = mapped_column(Float)
    baseline_price: Mapped[float] = mapped_column(Float)
    discount_percentage: Mapped[float] = mapped_column(Float)
    baseline_type: Mapped[str] = mapped_column(String(30))
    best_retailer: Mapped[str] = mapped_column(String(80))
    best_price: Mapped[float] = mapped_column(Float)
    deal_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    history_quality: Mapped[str] = mapped_column(String(10))
    notification_status: Mapped[str] = mapped_column(String(20), default="pending")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)  # full alert payload snapshot

    __table_args__ = (Index("ix_deal_product_ts", "product_id", "detected_at"),)


class AlertState(Base):
    """One row per product: drives alert de-duplication."""

    __tablename__ = "alert_states"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_alert_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_alert_discount: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_alert_severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_alert_retailer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    miss_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
