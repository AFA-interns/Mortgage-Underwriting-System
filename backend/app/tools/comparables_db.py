from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB

logger = logging.getLogger(__name__)

# Normalises common city name variations onto one canonical spelling, so
# "Bangalore" and "Bengaluru" (etc.) match the same stored rows regardless
# of which form a listing or a caller used.
_CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "mumbai": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "pune": "Pune",
    "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "jaipur": "Jaipur",
    "lucknow": "Lucknow",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "noida": "Noida",
    "thane": "Thane",
    "navi mumbai": "Navi Mumbai",
    "ghaziabad": "Ghaziabad",
    "faridabad": "Faridabad",
    "greater noida": "Greater Noida",
}


def normalize_property_type(property_type: str) -> str:
    """Normalize property type to a standard form for comparison."""
    value = str(property_type).lower().strip()

    if any(
        keyword in value
        for keyword in [
            "apartment",
            "flat",
            "residential flat",
            "residential apartment",
        ]
    ):
        return "apartment"

    if "independent house" in value or "independent floor" in value:
        return "independent house"

    if "villa" in value:
        return "villa"

    if "plot" in value or "land" in value:
        return "plot"

    return value


def _normalize_city(city: str) -> str:
    return _CITY_ALIASES.get(city.strip().lower(), city.strip())


def _shape_comparables(
    listings: list[Any],
    property_type: str,
    bhk: int | None,
    area_sqft: float | None,
    min_quality_score: float,
    max_results: int,
) -> list[dict[str, Any]]:
    """Filters and normalises raw PropertyListingDB/PropertyListingRow rows
    into the comparables shape property.py/property_valuation.py expect.
    Shared by both the async and sync query paths so they behave
    identically - this is pure, no I/O.
    """
    property_type_clean = normalize_property_type(property_type)
    comparables: list[dict[str, Any]] = []

    for listing in listings:
        listing_type = normalize_property_type(listing.property_type or "")

        # Property type must match (case-insensitive).
        if listing_type.lower() != property_type_clean.lower():
            continue

        # BHK must match when both are available.
        if bhk is not None and listing.bedrooms is not None and listing.bedrooms != bhk:
            continue

        # Area should normally be within ±20%.
        if area_sqft is not None and listing.area_sqft is not None:
            min_area = area_sqft * 0.80
            max_area = area_sqft * 1.20
            if not (min_area <= listing.area_sqft <= max_area):
                continue

        # Price must be usable.
        if listing.price is None or listing.price <= 0:
            continue

        # Quality score filter.
        quality_score = listing.data_quality_score or 0.0
        if quality_score < min_quality_score:
            continue

        # Calculate price per sqft if not already stored.
        price_per_sqft = listing.price_per_sqft
        if price_per_sqft is None and listing.area_sqft and listing.area_sqft > 0:
            price_per_sqft = listing.price / listing.area_sqft
        if price_per_sqft is None:
            continue

        comparables.append({
            # listing_id/title match the shape AVnester (app.tools.external_api)
            # and the local-median fallback (app.tools.local_comparables) both
            # use, so the frontend's comparables table (which keys rows on
            # listing_id and displays title) works the same regardless of
            # which of the three sources actually produced the valuation.
            "listing_id": listing.source_url or f"{listing.source}-{listing.id}",
            "title": f"{listing.property_type or 'Property'} in {listing.locality or listing.city}",
            "id": listing.id,
            "source": listing.source,
            "source_url": listing.source_url,
            "city": listing.city,
            "locality": listing.locality,
            "property_type": listing.property_type,
            "transaction_type": listing.transaction_type,
            "bhk": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "area_sqft": listing.area_sqft,
            "price_inr": listing.price,
            "price_per_sqft_inr": price_per_sqft,
            "furnishing": listing.furnishing,
            "floor": listing.floor,
            "total_floors": listing.total_floors,
            "parking": listing.parking,
            "data_quality_score": quality_score,
            "source_count": getattr(listing, "source_count", None) or 1,
            "imputed_fields": getattr(listing, "imputed_fields", None) or [],
        })

    # Sort by quality score (desc), then area similarity (asc).
    if area_sqft:
        comparables.sort(
            key=lambda item: (-item.get("data_quality_score", 0), abs((item["area_sqft"] or area_sqft) - area_sqft))
        )
    else:
        comparables.sort(key=lambda item: -item.get("data_quality_score", 0))

    return comparables[:max_results]


async def get_comparables(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
    min_quality_score: float = 40.0,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Async comparables lookup against the scraped property_listings table.

    Kept for property_data's own async scraper/ingestion scripts. Live
    request-serving code should use get_comparables_sync() instead - see
    its docstring for why (asyncpg has proven unreliable against local
    Postgres on at least one development machine; the sync psycopg path
    backing get_comparables_sync() has not).
    """
    if not city or not locality:
        return []

    city_normalized = _normalize_city(city)
    locality_clean = locality.strip()

    try:
        async with AsyncSessionLocal() as session:
            query = select(PropertyListingDB).where(
                PropertyListingDB.city.ilike(city_normalized),
                PropertyListingDB.locality.ilike(locality_clean),
                PropertyListingDB.transaction_type == "Sale",
            )
            result = await session.execute(query)
            listings = result.scalars().all()
            for listing in listings:
                session.expunge(listing)
    except Exception as e:
        logger.error(f"Database error in get_comparables: {e}")
        return []

    return _shape_comparables(listings, property_type, bhk, area_sqft, min_quality_score, max_results)


def get_comparables_sync(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
    min_quality_score: float = 40.0,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Comparables lookup for the (sync) LangGraph pipeline - property.py's
    comps_node and property_valuation.py both call this directly.

    Queries via app.services.property_db's sync (psycopg) engine rather
    than bridging to the async get_comparables() above. That's a
    deliberate choice, not just a style preference: on at least one
    development machine, asyncpg intermittently fails authentication
    against the exact same DATABASE_URL/credentials that the sync psycopg
    path connects with 100% reliably - confirmed by isolating every other
    variable (URL construction, SSL mode, connection pooling, the asyncio
    event loop policy, import order) without finding a reproducible
    trigger; the failure is decided once per process, before any of this
    module's code runs, which rules out a fix at this layer. Since the
    live pipeline only ever reads this table (writes come from the
    separate scraper/ingestion scripts, which can use the async path),
    reading it through the already-proven-reliable sync engine sidesteps
    the issue entirely instead of working around it.
    """
    if not city or not locality:
        return []

    from app.services.property_db import PropertyListingRow, _get_session_factory

    session_factory = _get_session_factory()
    if session_factory is None:
        return []

    city_normalized = _normalize_city(city)
    locality_clean = locality.strip()

    try:
        with session_factory() as session:
            query = select(PropertyListingRow).where(
                PropertyListingRow.city.ilike(city_normalized),
                PropertyListingRow.locality.ilike(locality_clean),
                PropertyListingRow.transaction_type == "Sale",
            )
            listings = session.scalars(query).all()
    except Exception as e:
        logger.warning(f"Database error in get_comparables_sync: {e}")
        return []

    return _shape_comparables(listings, property_type, bhk, area_sqft, min_quality_score, max_results)
