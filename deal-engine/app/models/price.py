from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigIntPK, utcnow

OBSERVED = "OBSERVED_HISTORY"
IMPORTED = "IMPORTED_HISTORY"
ESTIMATED = "ESTIMATED_HISTORY"


class PriceObservation(Base):
    """Append-only. Rows are never updated; every crawl result is a new row."""

    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    retailer_product_id: Mapped[int] = mapped_column(ForeignKey("retailer_products.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    price: Mapped[float] = mapped_column(Float)  # displayed price, original currency
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    price_inr: Mapped[float] = mapped_column(Float)  # displayed price normalised to INR
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)  # INR
    coupon_discount: Mapped[float | None] = mapped_column(Float, nullable=True)  # INR, as advertised
    coupon_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    membership_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # INR, never used for deals
    mrp_inr: Mapped[float | None] = mapped_column(Float, nullable=True)  # informational only
    effective_price: Mapped[float] = mapped_column(Float)  # INR: price + shipping - VERIFIED coupon
    availability: Mapped[bool] = mapped_column(Boolean, default=True)
    is_payable: Mapped[bool] = mapped_column(Boolean, default=True)  # False: EMI-only / subscription-only price
    seller: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default=OBSERVED)

    __table_args__ = (
        Index("ix_obs_rp_ts", "retailer_product_id", "timestamp"),
        Index("ix_obs_ts", "timestamp"),
    )


class DailyPrice(Base):
    """Daily roll-up of in-stock, payable effective prices (what the history engine reads)."""

    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    retailer_product_id: Mapped[int] = mapped_column(ForeignKey("retailer_products.id"))
    day: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default=OBSERVED)
    min_price: Mapped[float] = mapped_column(Float)
    max_price: Mapped[float] = mapped_column(Float)
    last_price: Mapped[float] = mapped_column(Float)
    obs_count: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("retailer_product_id", "day", "source", name="uq_daily_rp_day_src"),
        Index("ix_daily_day", "day"),
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    inr_per_unit: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(30), default="provider")
