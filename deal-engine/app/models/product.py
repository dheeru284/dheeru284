from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, BigIntPK, JSONType, utcnow


class Product(Base):
    """Canonical product (one specific model/variant, independent of retailer)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    manufacturer_part_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    normalized_attributes: Mapped[dict] = mapped_column(JSONType, default=dict)
    core_tokens: Mapped[list] = mapped_column(JSONType, default=list)
    image_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    listings: Mapped[list[RetailerProduct]] = relationship(back_populates="product")

    __table_args__ = (
        Index("ix_products_gtin", "gtin"),
        Index("ix_products_mpn", "manufacturer_part_number"),
        Index("ix_products_brand_category", "brand", "category"),
    )


class RetailerProduct(Base):
    """A listing of a product on one retailer."""

    __tablename__ = "retailer_products"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    retailer_id: Mapped[int] = mapped_column(ForeignKey("retailers.id"))
    retailer_product_id: Mapped[str] = mapped_column(String(160))
    product_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    mpn: Mapped[str | None] = mapped_column(String(80), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    seller: Mapped[str | None] = mapped_column(String(160), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mrp_inr: Mapped[float | None] = mapped_column(Float, nullable=True)  # informational ONLY, never a baseline
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_notes: Mapped[dict] = mapped_column(JSONType, default=dict)
    attributes: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Crawl scheduling
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher == crawled more often
    hot: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_crawl_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product: Mapped[Product | None] = relationship(back_populates="listings")

    __table_args__ = (
        UniqueConstraint("retailer_id", "retailer_product_id", name="uq_retailer_listing"),
        Index("ix_rp_product", "product_id"),
        Index("ix_rp_next_crawl", "active", "next_crawl_at"),
        Index("ix_rp_gtin", "gtin"),
    )
