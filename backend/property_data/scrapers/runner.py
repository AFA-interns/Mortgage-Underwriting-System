"""
CLI runner for the multi-source property scraper.

Usage:
    python -m property_data.scrapers.runner --city Bangalore --bhk 2
    python -m property_data.scrapers.runner --city Mumbai --locality "Andheri West" --bhk 3
    python -m property_data.scrapers.runner --city Hyderabad --bhk 2 --limit 30 --no-save
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from property_data.database.connection import AsyncSessionLocal, init_db
from property_data.scrapers.squareyards_v2 import SquareYardsScraperV2
from property_data.scrapers.housing import HousingScraper
from property_data.scrapers.magicbricks import MagicBricksScraper
from property_data.scrapers.merger import merge_sources
from property_data.scrapers.quality import get_quality_label


async def run_scraper(
    city: str,
    locality: str | None = None,
    bhk: int = 2,
    limit: int = 20,
    save_to_db: bool = True,
    sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Run the multi-source scraper.

    Args:
        city: City name
        locality: Optional locality filter
        bhk: Number of bedrooms
        limit: Max listings per source
        save_to_db: Whether to save results to PostgreSQL
        sources: List of sources to scrape (default: all)

    Returns:
        List of merged property listings
    """
    if sources is None:
        sources = ["square_yards", "housing", "magicbricks"]

    all_sources: dict[str, list[dict[str, Any]]] = {}

    # SquareYards
    if "square_yards" in sources:
        print("=" * 80)
        print(f"SCRAPING: SquareYards — {city} {locality or ''} {bhk} BHK")
        print("=" * 80)

        scraper = SquareYardsScraperV2(
            headless=True,
            min_delay=3.0,
            max_delay=7.0,
        )

        try:
            listings = await scraper.fetch_listings(
                city=city,
                locality=locality,
                bhk=bhk,
                limit=limit,
            )
            all_sources["square_yards"] = listings
            print(f"\n[SQUARE YARDS] Total: {len(listings)} listings")
        except Exception as exc:
            print(f"\n[SQUARE YARDS] Error: {exc}")
            all_sources["square_yards"] = []

    # Housing.com
    if "housing" in sources:
        print("\n" + "=" * 80)
        print(f"SCRAPING: Housing.com — {city} {locality or ''} {bhk} BHK")
        print("=" * 80)

        scraper = HousingScraper(
            headless=True,
            min_delay=3.0,
            max_delay=7.0,
        )

        try:
            listings = await scraper.fetch_listings(
                city=city,
                locality=locality,
                bhk=bhk,
                limit=limit,
            )
            all_sources["housing"] = listings
            print(f"\n[HOUSING.COM] Total: {len(listings)} listings")
        except Exception as exc:
            print(f"\n[HOUSING.COM] Error: {exc}")
            all_sources["housing"] = []

    # MagicBricks
    if "magicbricks" in sources:
        print("\n" + "=" * 80)
        print(f"SCRAPING: MagicBricks — {city} {locality or ''} {bhk} BHK")
        print("=" * 80)

        scraper = MagicBricksScraper(
            headless=True,
            min_delay=3.0,
            max_delay=7.0,
        )

        try:
            listings = await scraper.fetch_listings(
                city=city,
                locality=locality,
                bhk=bhk,
                limit=limit,
            )
            all_sources["magicbricks"] = listings
            print(f"\n[MAGICBRICKS] Total: {len(listings)} listings")
        except Exception as exc:
            print(f"\n[MAGICBRICKS] Error: {exc}")
            all_sources["magicbricks"] = []

    # Merge sources
    print("\n" + "=" * 80)
    print("MERGING SOURCES")
    print("=" * 80)

    merged = merge_sources(all_sources)

    print(f"\nTotal merged listings: {len(merged)}")

    # Print summary
    for i, listing in enumerate(merged[:10], 1):
        quality = listing.get("data_quality_score", 0)
        label = get_quality_label(quality)
        print(
            f"\n{i}. {listing.get('bedrooms')} BHK | "
            f"{listing.get('area_sqft', 0):,.0f} sqft | "
            f"INR {listing.get('price', 0):,.0f} | "
            f"{listing.get('locality', 'N/A')} | "
            f"Quality: {quality} ({label})"
        )

    # Save to database
    if save_to_db and merged:
        print("\n" + "=" * 80)
        print("SAVING TO DATABASE")
        print("=" * 80)

        await init_db()

        async with AsyncSessionLocal() as session:
            from property_data.database.models import PropertyListingDB

            saved = 0
            skipped = 0

            for listing in merged:
                # Check if already exists
                source_url = listing.get("source_url")
                if source_url:
                    from sqlalchemy import select
                    result = await session.execute(
                        select(PropertyListingDB).where(
                            PropertyListingDB.source_url == source_url
                        )
                    )
                    if result.scalar_one_or_none():
                        skipped += 1
                        continue

                # Create new record
                db_listing = PropertyListingDB(
                    source=listing.get("source", "unknown"),
                    source_url=listing.get("source_url"),
                    state=listing.get("state"),
                    city=listing.get("city"),
                    locality=listing.get("locality"),
                    pincode=listing.get("pincode"),
                    property_type=listing.get("property_type"),
                    transaction_type=listing.get("transaction_type"),
                    bedrooms=listing.get("bedrooms"),
                    bathrooms=listing.get("bathrooms"),
                    area_sqft=listing.get("area_sqft"),
                    price=listing.get("price"),
                    price_per_sqft=listing.get("price_per_sqft"),
                    furnishing=listing.get("furnishing"),
                    floor=listing.get("floor"),
                    total_floors=listing.get("total_floors"),
                    property_age=listing.get("property_age"),
                    parking=listing.get("parking"),
                    listing_date=listing.get("listing_date"),
                    data_quality_score=listing.get("data_quality_score", 0.0),
                    quality_completeness=listing.get("quality_completeness", 0.0),
                    quality_freshness=listing.get("quality_freshness", 0.0),
                    source_count=listing.get("source_count", 1),
                    imputed_fields=listing.get("imputed_fields", []),
                    sources=listing.get("sources", []),
                )
                session.add(db_listing)
                saved += 1

            await session.commit()
            print(f"Saved: {saved} | Skipped (duplicates): {skipped}")

    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Multi-source property scraper"
    )
    parser.add_argument(
        "--city",
        required=True,
        help="City name (e.g., Bangalore, Mumbai)",
    )
    parser.add_argument(
        "--locality",
        default=None,
        help="Locality filter (e.g., 'Whitefield')",
    )
    parser.add_argument(
        "--bhk",
        type=int,
        default=2,
        help="Number of bedrooms",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max listings per source",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save to database",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["square_yards"],
        help="Sources to scrape",
    )

    args = parser.parse_args()

    results = asyncio.run(
        run_scraper(
            city=args.city,
            locality=args.locality,
            bhk=args.bhk,
            limit=args.limit,
            save_to_db=not args.no_save,
            sources=args.sources,
        )
    )

    # Also save to JSON for inspection
    output_file = f"data/scraped_{args.city.lower()}_{args.bhk}bhk.json"
    from pathlib import Path

    Path("data").mkdir(exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
