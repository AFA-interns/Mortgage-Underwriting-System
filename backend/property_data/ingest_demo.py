import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.scrapers.demo_scraper import DemoPropertyScraper
from property_data.pipeline import clean_listing
from property_data.database.connection import AsyncSessionLocal
from property_data.database.repository import (
    save_listing,
    listing_exists,
)


async def main():

    scraper = DemoPropertyScraper()

    raw_listings = await scraper.fetch_listings(
        city="Bangalore",
        locality="Whitefield",
    )

    async with AsyncSessionLocal() as session:

        for raw in raw_listings:

            if await listing_exists(
                session,
                raw.get("source_url"),
            ):
                print(
                    f"SKIPPED DUPLICATE: "
                    f"{raw.get('source_url')}"
                )
                continue

            cleaned = clean_listing(raw)

            saved = await save_listing(
                session,
                cleaned,
            )

            print(
                f"SAVED: ID={saved.id}, "
                f"{saved.city}, "
                f"{saved.locality}, "
                f"₹{saved.price}"
            )


if __name__ == "__main__":
    asyncio.run(main())