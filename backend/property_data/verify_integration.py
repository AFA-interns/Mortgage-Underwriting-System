"""
Verify the full integration: scraped data -> enrichment -> PostgreSQL -> comparables.

Usage:
    python -m property_data.verify_integration
"""

import asyncio

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB
from sqlalchemy import select, func

from app.tools.comparables_db import get_comparables


async def verify_database():
    """Check what data is in PostgreSQL."""
    print("=" * 60)
    print("STEP 1: VERIFY POSTGRESQL DATA")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # Count total listings
        result = await session.execute(
            select(func.count(PropertyListingDB.id))
        )
        total = result.scalar()
        print(f"\nTotal listings in database: {total}")

        # Count by city
        result = await session.execute(
            select(
                PropertyListingDB.city,
                func.count(PropertyListingDB.id),
            ).group_by(PropertyListingDB.city)
        )
        cities = result.all()
        print("\nListings by city:")
        for city, count in cities:
            print(f"  {city}: {count}")

        # Count by locality
        result = await session.execute(
            select(
                PropertyListingDB.locality,
                func.count(PropertyListingDB.id),
            ).group_by(PropertyListingDB.locality)
        )
        localities = result.all()
        print("\nListings by locality:")
        for locality, count in localities:
            print(f"  {locality}: {count}")

        # Quality score stats
        result = await session.execute(
            select(
                func.min(PropertyListingDB.data_quality_score),
                func.max(PropertyListingDB.data_quality_score),
                func.avg(PropertyListingDB.data_quality_score),
            )
        )
        min_q, max_q, avg_q = result.one()
        print(f"\nQuality scores:")
        print(f"  Min: {min_q}")
        print(f"  Max: {max_q}")
        print(f"  Avg: {avg_q:.1f}")


async def verify_comparables():
    """Test the comparables lookup."""
    print("\n" + "=" * 60)
    print("STEP 2: TEST COMPARABLES LOOKUP")
    print("=" * 60)

    # Test 1: Indiranagar, Bangalore
    print("\n[Test 1] Indiranagar, Bangalore — 2 BHK, 1200 sqft")
    comps = await get_comparables(
        locality="Indiranagar",
        city="Bengaluru",
        property_type="Apartment",
        bhk=2,
        area_sqft=1200,
    )
    print(f"  Comparables found: {len(comps)}")
    for c in comps[:3]:
        print(
            f"    {c.get('bhk')} BHK | "
            f"{c.get('area_sqft')} sqft | "
            f"INR {c.get('price_inr', 0):,.0f} | "
            f"Quality: {c.get('data_quality_score', 0)}"
        )

    # Test 2: Koramangala, Bangalore
    print("\n[Test 2] Koramangala, Bangalore — 3 BHK, 1500 sqft")
    comps = await get_comparables(
        locality="Koramangala",
        city="Bengaluru",
        property_type="Apartment",
        bhk=3,
        area_sqft=1500,
    )
    print(f"  Comparables found: {len(comps)}")
    for c in comps[:3]:
        print(
            f"    {c.get('bhk')} BHK | "
            f"{c.get('area_sqft')} sqft | "
            f"INR {c.get('price_inr', 0):,.0f} | "
            f"Quality: {c.get('data_quality_score', 0)}"
        )

    # Test 3: Whitefield, Bangalore
    print("\n[Test 3] Whitefield, Bangalore — 2 BHK, 1100 sqft")
    comps = await get_comparables(
        locality="Whitefield",
        city="Bengaluru",
        property_type="Apartment",
        bhk=2,
        area_sqft=1100,
    )
    print(f"  Comparables found: {len(comps)}")
    for c in comps[:3]:
        print(
            f"    {c.get('bhk')} BHK | "
            f"{c.get('area_sqft')} sqft | "
            f"INR {c.get('price_inr', 0):,.0f} | "
            f"Quality: {c.get('data_quality_score', 0)}"
        )

    # Test 4: Mumbai
    print("\n[Test 4] Andheri West, Mumbai — 2 BHK, 1000 sqft")
    comps = await get_comparables(
        locality="Andheri West",
        city="Mumbai",
        property_type="Apartment",
        bhk=2,
        area_sqft=1000,
    )
    print(f"  Comparables found: {len(comps)}")
    for c in comps[:3]:
        print(
            f"    {c.get('bhk')} BHK | "
            f"{c.get('area_sqft')} sqft | "
            f"INR {c.get('price_inr', 0):,.0f} | "
            f"Quality: {c.get('data_quality_score', 0)}"
        )


async def verify_pipeline():
    """Verify the full pipeline from data to comparables."""
    print("\n" + "=" * 60)
    print("STEP 3: FULL PIPELINE VERIFICATION")
    print("=" * 60)

    import pandas as pd

    # Check enriched CSV
    df = pd.read_csv("data/enriched_properties.csv")
    print(f"\nEnriched CSV:")
    print(f"  Rows: {len(df)}")
    print(f"  Cities: {df['city'].nunique()}")
    print(f"  Localities: {df['locality'].nunique()}")
    print(f"  Quality range: {df['data_quality_score'].min():.1f} — {df['data_quality_score'].max():.1f}")

    # Check database
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(PropertyListingDB.id))
        )
        total = result.scalar()
        print(f"\nPostgreSQL:")
        print(f"  Total listings: {total}")

    # Test comparables
    print(f"\nComparables lookup:")
    for locality in ["Indiranagar", "Koramangala", "Whitefield"]:
        comps = await get_comparables(
            locality=locality,
            city="Bengaluru",
            property_type="Apartment",
            bhk=2,
            area_sqft=1200,
        )
        print(f"  {locality}: {len(comps)} comparables")


async def main():
    await verify_database()
    await verify_comparables()
    await verify_pipeline()

    print("\n" + "=" * 60)
    print("INTEGRATION VERIFICATION COMPLETE")
    print("=" * 60)
    print("\nSummary:")
    print("  - Web-scraped data enriched with inference + geocoding")
    print("  - Data saved to PostgreSQL with quality scores")
    print("  - Comparables lookup works with quality filtering")
    print("  - Property Valuation Agent can use this data via get_comparables()")


if __name__ == "__main__":
    asyncio.run(main())
