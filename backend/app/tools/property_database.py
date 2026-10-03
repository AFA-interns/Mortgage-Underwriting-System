from __future__ import annotations

from typing import Any

from property_data.database.connection import AsyncSessionLocal
from property_data.database.repository import find_comparables


async def get_database_comparables(
    city: str,
    locality: str,
    bedrooms: int | None = None,
) -> list[dict[str, Any]]:

    async with AsyncSessionLocal() as session:

        properties = await find_comparables(
            session=session,
            city=city,
            locality=locality,
            bedrooms=bedrooms,
        )

        return [
            {
                "id": p.id,
                "source": p.source,
                "source_url": p.source_url,
                "locality": p.locality,
                "city": p.city,
                "property_type": p.property_type,
                "bhk": p.bedrooms,
                "area_sqft": p.area_sqft,
                "price_inr": p.price,
                "price_per_sqft": p.price_per_sqft,
                "transaction_type": p.transaction_type,
            }
            for p in properties
        ]