"""Local comparable-sales database (PostgreSQL) — a second valuation source
alongside the live AVnester API (app.services.avnester). Populated by
scraping public listing sites (see backend/property_data/ and
backend/scripts/ingest_squareyards.py); property valuation reconciles
whichever of the two sources has usable data for the subject property.

Uses the same DATABASE_URL as the application store (app.services.db), but
its own engine and table: this is bulk, append-only reference data, not
per-application transactional data, so it doesn't belong to
PostgresApplicationStore and has no in-memory fallback. When no database is
configured, or it's unreachable, every function here degrades to "no local
comparables found" rather than raising - the same as AVnester returning no
listings for a location.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class PropertyListingRow(Base):
    """One scraped comparable listing. Mirrors property_data's cleaned
    listing shape (backend/property_data/cleaners/property_cleaner.py)."""

    __tablename__ = "property_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    locality: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_per_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    furnishing: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


_session_factory: sessionmaker | None = None
_init_attempted = False


def _get_session_factory() -> sessionmaker | None:
    global _session_factory, _init_attempted
    if _session_factory is not None or _init_attempted:
        return _session_factory
    _init_attempted = True

    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return None
    try:
        from app.services.db import ensure_database, normalise_url

        url = normalise_url(raw_url)
        ensure_database(url)
        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        _session_factory = sessionmaker(engine, expire_on_commit=False)
    except Exception as exc:
        logger.warning("Local property-comparables database unavailable: %s", exc)
        return None
    return _session_factory


def _row_to_dict(row: PropertyListingRow) -> dict[str, Any]:
    return {
        "source": row.source,
        "source_url": row.source_url,
        "city": row.city,
        "locality": row.locality,
        "property_type": row.property_type,
        "bedrooms": row.bedrooms,
        "area_sqft": row.area_sqft,
        "price": row.price,
        "price_per_sqft": row.price_per_sqft,
    }


def save_listings(listings: list[dict[str, Any]]) -> dict[str, int]:
    """Inserts cleaned listings (property_data.pipeline.clean_listing output),
    skipping ones already stored under the same source_url. Returns
    {"inserted": n, "duplicates": n}; {"inserted": 0, "duplicates": 0} if no
    database is configured."""
    Session = _get_session_factory()
    if Session is None:
        return {"inserted": 0, "duplicates": 0}

    inserted = duplicates = 0
    with Session.begin() as s:
        for item in listings:
            source_url = item.get("source_url")
            if source_url and s.scalar(
                select(PropertyListingRow.id).where(PropertyListingRow.source_url == source_url)
            ):
                duplicates += 1
                continue
            s.add(PropertyListingRow(
                source=item.get("source", "unknown"),
                source_url=source_url,
                state=item.get("state"),
                city=item.get("city") or "",
                locality=item.get("locality"),
                pincode=item.get("pincode"),
                property_type=item.get("property_type"),
                transaction_type=item.get("transaction_type"),
                bedrooms=item.get("bedrooms"),
                bathrooms=item.get("bathrooms"),
                area_sqft=item.get("area_sqft"),
                price=item.get("price"),
                price_per_sqft=item.get("price_per_sqft"),
                furnishing=item.get("furnishing"),
                floor=item.get("floor"),
                total_floors=item.get("total_floors"),
                property_age=item.get("property_age"),
                parking=item.get("parking"),
                listing_date=item.get("listing_date"),
                collected_at=datetime.now(UTC),
            ))
            inserted += 1
    return {"inserted": inserted, "duplicates": duplicates}


def find_comparables(
    city: str, locality: str | None = None, bedrooms: int | None = None
) -> list[dict[str, Any]]:
    """Comparable sale listings scoped to city (and locality/bedrooms when
    given), case-insensitive. Returns [] if no database is configured,
    unreachable, or nothing matches - callers treat that the same as
    "no comparables found", not an error."""
    Session = _get_session_factory()
    if Session is None or not city:
        return []

    query = select(PropertyListingRow).where(
        PropertyListingRow.city.ilike(city.strip()),
        PropertyListingRow.transaction_type == "Sale",
    )
    if locality:
        query = query.where(PropertyListingRow.locality.ilike(locality.strip()))
    if bedrooms is not None:
        query = query.where(PropertyListingRow.bedrooms == bedrooms)

    try:
        with Session() as s:
            return [_row_to_dict(r) for r in s.scalars(query).all()]
    except Exception as exc:
        logger.warning("Local property-comparables lookup failed: %s", exc)
        return []
