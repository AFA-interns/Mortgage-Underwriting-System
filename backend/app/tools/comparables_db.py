from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB


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


import logging

logger = logging.getLogger(__name__)


async def get_comparables(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
    min_quality_score: float = 40.0,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    Get comparable properties from PostgreSQL.

    Data sources include:
    - SquareYards, Housing.com, MagicBricks (via scraper pipeline)
    - Enriched CSV imports
    - Any source stored in property_listings table

    Args:
        locality: Locality or neighborhood name
        city: City name
        property_type: Property type (Apartment, Villa, etc.)
        bhk: Number of bedrooms
        area_sqft: Subject property area in sqft
        min_quality_score: Minimum data quality score (0-100). Listings
            below this threshold are excluded. Default 40.0.
        max_results: Maximum number of comparables to return. Default 20.

    Returns:
        List of comparable property dicts, sorted by quality score
        then area similarity. Each dict includes data_quality_score.
    """

    if not city or not locality:
        return []

    city_clean = city.strip()
    locality_clean = locality.strip()

    # Normalize city name variations
    city_aliases = {
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
    city_normalized = city_aliases.get(city_clean.lower(), city_clean)

    property_type_clean = normalize_property_type(property_type)

    try:
        async with AsyncSessionLocal() as session:
            query = select(PropertyListingDB).where(
                PropertyListingDB.city.ilike(city_normalized),
                PropertyListingDB.locality.ilike(locality_clean),
                PropertyListingDB.transaction_type == "Sale",
            )

            result = await session.execute(query)
            listings = result.scalars().all()

            # Expunge all objects from session to avoid session-related issues
            for listing in listings:
                session.expunge(listing)

    except Exception as e:
        logger.error(f"Database error in get_comparables: {e}")
        return []

    comparables: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # Filter and normalize PostgreSQL records
    # ---------------------------------------------------------

    for listing in listings:

        listing_type = normalize_property_type(
            listing.property_type or ""
        )

        # Property type must match (case-insensitive).
        if listing_type.lower() != property_type_clean.lower():
            continue

        # BHK must match when both are available.
        if (
            bhk is not None
            and listing.bedrooms is not None
            and listing.bedrooms != bhk
        ):
            continue

        # Area should normally be within ±20%.
        if (
            area_sqft is not None
            and listing.area_sqft is not None
        ):
            min_area = area_sqft * 0.80
            max_area = area_sqft * 1.20

            if not (
                min_area
                <= listing.area_sqft
                <= max_area
            ):
                continue

        # Price must be usable.
        if (
            listing.price is None
            or listing.price <= 0
        ):
            continue

        # Quality score filter.
        quality_score = listing.data_quality_score or 0.0
        if quality_score < min_quality_score:
            continue

        # Calculate price per sqft if not already stored.
        price_per_sqft = listing.price_per_sqft

        if (
            price_per_sqft is None
            and listing.area_sqft
            and listing.area_sqft > 0
        ):
            price_per_sqft = (
                listing.price
                / listing.area_sqft
            )

        if price_per_sqft is None:
            continue

        comparables.append(
            {
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
                "source_count": listing.source_count or 1,
                "imputed_fields": listing.imputed_fields or [],
            }
        )

    # ---------------------------------------------------------
    # Sort by quality score (desc), then area similarity (asc)
    # ---------------------------------------------------------

    if area_sqft:
        comparables.sort(
            key=lambda item: (
                -item.get("data_quality_score", 0),
                abs(
                    (item["area_sqft"] or area_sqft)
                    - area_sqft
                ),
            )
        )
    else:
        comparables.sort(
            key=lambda item: -item.get("data_quality_score", 0)
        )

    # Limit results
    return comparables[:max_results]


def get_comparables_sync(**kwargs: Any) -> list[dict[str, Any]]:
    """Sync bridge for get_comparables(), safe whether or not the calling
    thread already has a running asyncio event loop.

    Our LangGraph nodes are plain sync functions (matching the rest of the
    pipeline's sync architecture), but some callers reach them from inside
    an `async def` FastAPI endpoint that never itself awaits anything - the
    endpoint still runs on the event loop thread, so a plain
    `asyncio.run(get_comparables(...))` there would raise ("asyncio.run()
    cannot be called from a running event loop"). When no loop is running,
    asyncio.run() is used directly; when one is, the coroutine runs on a
    separate thread with its own loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_comparables(**kwargs))

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, get_comparables(**kwargs)).result()