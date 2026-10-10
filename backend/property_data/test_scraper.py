import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.scrapers.demo_scraper import DemoPropertyScraper
from property_data.pipeline import clean_listing


async def main():

    scraper = DemoPropertyScraper()

    raw_listings = await scraper.fetch_listings(
        city="Bangalore",
        locality="Whitefield",
    )

    print(f"RAW LISTINGS: {len(raw_listings)}")

    for raw in raw_listings:
        cleaned = clean_listing(raw)

        print("\nRAW:")
        print(raw)

        print("\nCLEANED:")
        print(cleaned)


if __name__ == "__main__":
    asyncio.run(main())