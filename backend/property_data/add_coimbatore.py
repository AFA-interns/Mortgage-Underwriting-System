"""
Add Coimbatore property listings to PostgreSQL.

Usage:
    python -m property_data.add_coimbatore
"""

import asyncio
import random

from sqlalchemy import select

from property_data.database.connection import AsyncSessionLocal, init_db
from property_data.database.models import PropertyListingDB
from property_data.scrapers.quality import compute_quality_score


COIMBATORE_LOCALITIES = [
    ("Saravanampatti", 5500, 8500),
    ("Gandhipuram", 7000, 11000),
    ("RS Puram", 6500, 10000),
    ("Saibaba Colony", 6000, 9500),
    ("Vadavalli", 5000, 8000),
    ("Thudiyalur", 4500, 7000),
    ("Peelamedu", 5500, 8500),
    ("Singanallur", 4000, 6500),
    ("Kalapatti", 4000, 6000),
    ("Kovaipudur", 4500, 7000),
]


def generate_listings():
    """Generate realistic Coimbatore property listings."""
    listings = []
    for locality, min_ppsf, max_ppsf in COIMBATORE_LOCALITIES:
        for _ in range(5):
            bhk = random.choice([1, 2, 2, 2, 3, 3, 3, 4])
            area = random.randint(500, 2500)
            ppsf = random.randint(min_ppsf, max_ppsf)
            price = area * ppsf
            age = random.randint(0, 15)

            listing = {
                "source": "synthetic",
                "source_url": None,
                "state": "Tamil Nadu",
                "city": "Coimbatore",
                "locality": locality,
                "pincode": None,
                "property_type": "Apartment",
                "transaction_type": "Sale",
                "bedrooms": bhk,
                "bathrooms": None,
                "area_sqft": area,
                "price": price,
                "price_per_sqft": ppsf,
                "furnishing": None,
                "floor": None,
                "total_floors": None,
                "property_age": age,
                "parking": None,
                "listing_date": None,
            }

            quality = compute_quality_score(listing, source_count=1)
            listing["data_quality_score"] = quality["quality_score"]
            listing["quality_completeness"] = quality["completeness"]
            listing["quality_freshness"] = quality["freshness"]
            listing["source_count"] = 1
            listing["imputed_fields"] = quality["imputed_fields"]
            listing["sources"] = ["synthetic"]

            listings.append(listing)

    return listings


async def main():
    print("=" * 60)
    print("ADDING COIMBATORE LISTINGS")
    print("=" * 60)

    listings = generate_listings()
    print(f"\nGenerated {len(listings)} Coimbatore listings")

    await init_db()

    async with AsyncSessionLocal() as session:
        imported = 0
        skipped = 0

        for listing in listings:
            # Check if already exists
            result = await session.execute(
                select(PropertyListingDB).where(
                    PropertyListingDB.city == "Coimbatore",
                    PropertyListingDB.locality == listing["locality"],
                    PropertyListingDB.bedrooms == listing["bedrooms"],
                    PropertyListingDB.area_sqft == listing["area_sqft"],
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
    print(f"\nCoimbatore listings now in database: {imported + skipped}")


if __name__ == "__main__":
    asyncio.run(main())
