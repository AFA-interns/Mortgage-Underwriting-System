"""One-off CLI tool: scrapes Square Yards listing pages for a city, cleans
them, and stores them in the local comparables database (property_listings)
that app.tools.local_comparables reads from.

This performs real HTTP requests against a live, third-party website — run
it deliberately, not from a test suite or on every startup. It is not part
of the request-serving app; nothing here is imported by app.main.

    cd backend
    .\venv\Scripts\python.exe scripts/ingest_squareyards.py --city Bangalore --bhk 2 --limit 12

Requires DATABASE_URL (backend/.env) to point at a reachable PostgreSQL
instance - this writes directly via app.services.property_db, which creates
the property_listings table on first use if it doesn't exist yet.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402  (loads backend/.env)
from app.services.property_db import save_listings  # noqa: E402
from property_data.pipeline import clean_listing  # noqa: E402
from property_data.scrapers.squareyards_scraper import SquareYardsScraper  # noqa: E402


async def run(city: str, bhk: int, limit: int) -> None:
    scraper = SquareYardsScraper(city=city, bhk=bhk)
    raw_records = await scraper.scrape(limit=limit)
    print(f"\nScraped {len(raw_records)} raw listing(s) for {city}, {bhk} BHK.")

    cleaned = [clean_listing(r) for r in raw_records]
    result = save_listings(cleaned)

    print("\n" + "=" * 50)
    print("SQUARE YARDS INGESTION")
    print("=" * 50)
    print(f"Scraped   : {len(raw_records)}")
    print(f"Inserted  : {result['inserted']}")
    print(f"Duplicates: {result['duplicates']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Bangalore", help="City to scrape (default: Bangalore)")
    parser.add_argument("--bhk", type=int, default=2, help="Bedroom count to search (default: 2)")
    parser.add_argument("--limit", type=int, default=12, help="Max listing pages to fetch (default: 12)")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL", "").strip():
        print("DATABASE_URL is not set (backend/.env) - nothing would be saved. Aborting.")
        raise SystemExit(1)

    asyncio.run(run(args.city, args.bhk, args.limit))


if __name__ == "__main__":
    main()
