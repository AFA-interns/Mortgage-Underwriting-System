"""
Add targeted Bengaluru locality listings to PostgreSQL.

Adds listings for Indiranagar, Bellandur, and Koramangala
to support all 4 mock test scenarios.

Usage:
    python -m property_data.add_bengaluru_localities
"""

import asyncio

from sqlalchemy import select

from property_data.database.connection import AsyncSessionLocal, init_db
from property_data.database.models import PropertyListingDB
from property_data.scrapers.quality import compute_quality_score


# Targeted listings for each locality
LOCALITY_DATA = {
    "Indiranagar": {
        "min_ppsf": 12000,
        "max_ppsf": 18000,
        "areas": [1200, 1300, 1400, 1500, 1600, 1700],
        "bhk": [2, 3],
    },
    "Bellandur": {
        "min_ppsf": 8000,
        "max_ppsf": 14000,
        "areas": [1000, 1100, 1200, 1300, 1400, 1500],
        "bhk": [2, 3],
    },
    "Koramangala": {
        "min_ppsf": 11000,
        "max_ppsf": 16000,
        "areas": [1100, 1200, 1300, 1400, 1500, 1600],
        "bhk": [2, 3],
    },
}


def generate_listings():
    """Generate targeted listings for each locality."""
    listings = []

    for locality, config in LOCALITY_DATA.items():
        for area in config["areas"]:
            for bhk in config["bhk"]:
                for ppsf in range(config["min_ppsf"], config["max_ppsf"] + 1, 1000):
                    listing = {
                        "source": "targeted",
                        "source_url": None,
                        "state": "Karnataka",
                        "city": "Bengaluru",
                        "locality": locality,
                        "pincode": None,
                        "property_type": "Apartment",
                        "transaction_type": "Sale",
                        "bedrooms": bhk,
                        "bathrooms": bhk,
                        "area_sqft": float(area),
                        "price": float(area * ppsf),
                        "price_per_sqft": float(ppsf),
                        "furnishing": "Unfurnished",
                        "floor": 3,
                        "total_floors": 10,
                        "property_age": 3,
                        "parking": 1,
                        "listing_date": None,
                    }

                    quality = compute_quality_score(listing, source_count=1)
                    listing["data_quality_score"] = quality["quality_score"]
                    listing["quality_completeness"] = quality["completeness"]
                    listing["quality_freshness"] = quality["freshness"]
                    listing["source_count"] = 1
                    listing["imputed_fields"] = quality["imputed_fields"]
                    listing["sources"] = ["targeted"]

                    listings.append(listing)

    return listings


async def main():
    print("=" * 60)
    print("ADDING BENGALURU LOCALITY LISTINGS")
    print("=" * 60)

    listings = generate_listings()
    print(f"\nGenerated {len(listings)} targeted listings")

    await init_db()

    async with AsyncSessionLocal() as session:
        imported = 0
        skipped = 0

        for listing in listings:
            # Check if already exists
            result = await session.execute(
                select(PropertyListingDB).where(
                    PropertyListingDB.city == "Bengaluru",
                    PropertyListingDB.locality == listing["locality"],
                    PropertyListingDB.bedrooms == listing["bedrooms"],
                    PropertyListingDB.area_sqft == listing["area_sqft"],
                    PropertyListingDB.price_per_sqft == listing["price_per_sqft"],
                )
            )

            if result.scalar_one_or_none():
                skipped += 1
                continue

            db_listing = PropertyListingDB(
                source=listing["source"],
                source_url=listing["source_url"],
                state=listing["state"],
                city=listing["city"],
                locality=listing["locality"],
                pincode=listing["pincode"],
                property_type=listing["property_type"],
                transaction_type="Sale",
                bedrooms=listing["bedrooms"],
                bathrooms=listing["bathrooms"],
                area_sqft=listing["area_sqft"],
                price=listing["price"],
                price_per_sqft=listing["price_per_sqft"],
                furnishing=listing["furnishing"],
                floor=listing["floor"],
                total_floors=listing["total_floors"],
                property_age=listing["property_age"],
                parking=listing["parking"],
                listing_date=None,
                data_quality_score=listing["data_quality_score"],
                quality_completeness=listing["quality_completeness"],
                quality_freshness=listing["quality_freshness"],
                source_count=1,
                imputed_fields=listing["imputed_fields"],
                sources=listing["sources"],
            )
            session.add(db_listing)
            imported += 1

        await session.commit()

    print(f"\nImported: {imported}")
    print(f"Skipped: {skipped}")

    # Verify
    async with AsyncSessionLocal() as session:
        for locality in LOCALITY_DATA.keys():
            result = await session.execute(
                select(PropertyListingDB).where(
                    PropertyListingDB.locality == locality
                )
            )
            count = len(result.scalars().all())
            print(f"  {locality}: {count} listings")


if __name__ == "__main__":
    asyncio.run(main())
