from __future__ import annotations

from typing import Any

from sqlalchemy import select

from property_data.database.connection import (
    AsyncSessionLocal,
)

from property_data.database.models import (
    PropertyListingDB,
)


def normalize_property_type(
    property_type: str,
) -> str:

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

    if "independent house" in value:
        return "independent house"

    if "villa" in value:
        return "villa"

    if "plot" in value:
        return "plot"

    return value


async def get_comparables(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
) -> list[dict[str, Any]]:
    """
    Get comparable properties from PostgreSQL.

    Data sources currently include:
    - Square Yards ingested listings
    - Other property listings stored in property_listings
    """

    if not city or not locality:
        return []

    city_clean = city.strip().lower()
    locality_clean = locality.strip().lower()

    property_type_clean = normalize_property_type(
        property_type
    )

    async with AsyncSessionLocal() as session:

        query = select(PropertyListingDB).where(
            PropertyListingDB.city.ilike(city_clean),
            PropertyListingDB.locality.ilike(
                locality_clean
            ),
            PropertyListingDB.transaction_type == "Sale",
        )

        result = await session.execute(query)

        listings = result.scalars().all()

    comparables = []

    # ---------------------------------------------------------
    # Filter and normalize PostgreSQL records
    # ---------------------------------------------------------

    for listing in listings:

        listing_type = normalize_property_type(
            listing.property_type or ""
        )

        # Property type must match.
        if listing_type != property_type_clean:
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
                "transaction_type": (
                    listing.transaction_type
                ),
                "bhk": listing.bedrooms,
                "bathrooms": listing.bathrooms,
                "area_sqft": listing.area_sqft,
                "price_inr": listing.price,
                "price_per_sqft_inr": price_per_sqft,
                "furnishing": listing.furnishing,
                "floor": listing.floor,
                "total_floors": listing.total_floors,
                "parking": listing.parking,
            }
        )

    # ---------------------------------------------------------
    # Sort by similarity of area
    # ---------------------------------------------------------

    if area_sqft:

        comparables.sort(
            key=lambda item: abs(
                (item["area_sqft"] or area_sqft)
                - area_sqft
            )
        )

    return comparables