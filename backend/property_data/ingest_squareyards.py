import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB
from property_data.database.repository import listing_exists
from property_data.scrapers.squareyards_scraper import SquareYardsScraper


async def main():
    scraper = SquareYardsScraper(
        city="Bangalore",
        bhk=2,
    )

    records = await scraper.scrape()

    print(f"\nSCRAPED RECORDS: {len(records)}")

    inserted = 0
    duplicates = 0

    async with AsyncSessionLocal() as session:

        for record in records:

            source_url = record.get("source_url")

            if await listing_exists(session, source_url):
                duplicates += 1
                continue

            listing = PropertyListingDB(
                source="square_yards",
                source_url=record.get("source_url"),
                state=record.get("state"),
                city=record.get("city"),
                locality=record.get("locality"),
                pincode=record.get("pincode"),
                property_type=record.get("property_type"),
                transaction_type=record.get("transaction_type"),
                bedrooms=record.get("bedrooms"),
                bathrooms=record.get("bathrooms"),
                area_sqft=record.get("area_sqft"),
                price=record.get("price"),
                price_per_sqft=record.get("price_per_sqft"),
                furnishing=record.get("furnishing"),
                floor=record.get("floor"),
                total_floors=record.get("total_floors"),
                property_age=record.get("property_age"),
                parking=record.get("parking"),
                listing_date=record.get("listing_date"),
            )

            session.add(listing)
            inserted += 1

        await session.commit()

    print("\n" + "=" * 50)
    print("SQUARE YARDS DATABASE INGESTION")
    print("=" * 50)

    print(f"Scraped records : {len(records)}")
    print(f"Inserted        : {inserted}")
    print(f"Duplicates      : {duplicates}")

    print("\nDONE.")


if __name__ == "__main__":
    asyncio.run(main())