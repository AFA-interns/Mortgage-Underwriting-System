"""
Replace the PostgreSQL property_listings table with the new dataset.

1. Clears all existing data
2. Imports the new india_properties_clean.csv
3. Maps columns to the database schema
4. Computes quality scores
5. Verifies the import

Usage:
    python -m property_data.replace_dataset
"""

import asyncio

import pandas as pd
from sqlalchemy import text

from property_data.database.connection import AsyncSessionLocal, engine, init_db
from property_data.database.models import PropertyListingDB
from property_data.scrapers.quality import compute_quality_score


# Column mapping from CSV to database
COLUMN_MAP = {
    "property_id": None,  # Will use auto-increment
    "title": None,
    "project_name": None,
    "property_type": "property_type",
    "sub_type": None,
    "city": "city",
    "state": "state",
    "region": None,
    "locality": "locality",
    "sublocality": None,
    "price_inr": "price",
    "price_display": None,
    "area_sqft": "area_sqft",
    "area_type": None,
    "price_per_sqft": "price_per_sqft",
    "bhk": "bedrooms",
    "bathrooms": "bathrooms",
    "floor_number": "floor",
    "total_floors": "total_floors",
    "facing": None,
    "parking_spaces": "parking",
    "parking_type": None,
    "possession_status": None,
    "flooring": None,
    "additional_spaces": None,
    "latitude": None,
    "longitude": None,
    "listing_url": "source_url",
    "description": None,
    "source_platform": "source",
    "facing_clean": None,
    "is_vastu_compliant": None,
    "floor_ratio": None,
    "is_ground_floor": None,
    "is_high_rise": None,
    "has_parking": None,
    "has_covered_parking": None,
    "possession_clean": None,
    "is_ready_to_move": None,
    "price_lakhs": None,
    "price_crores": None,
    "log_price": None,
    "log_area": None,
}


def safe_int(value, default=None):
    """Safely convert to int, handling out-of-range and invalid values."""
    if pd.isna(value):
        return default
    try:
        result = int(float(value))
        # Clamp to int32 range
        if result > 2147483647:
            return default
        if result < -2147483648:
            return default
        return result
    except (ValueError, TypeError, OverflowError):
        return default


def safe_float(value, default=None):
    """Safely convert to float, handling invalid values."""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


def map_listing(row: pd.Series) -> dict:
    """Map a CSV row to the database schema."""
    listing = {
        "source": str(row.get("source_platform", "unknown")),
        "source_url": str(row.get("listing_url")) if pd.notna(row.get("listing_url")) else None,
        "state": str(row.get("state")) if pd.notna(row.get("state")) else None,
        "city": str(row.get("city")) if pd.notna(row.get("city")) else None,
        "locality": str(row.get("locality")) if pd.notna(row.get("locality")) else None,
        "pincode": None,
        "property_type": str(row.get("property_type")) if pd.notna(row.get("property_type")) else None,
        "transaction_type": "Sale",
        "bedrooms": safe_int(row.get("bhk")),
        "bathrooms": safe_int(row.get("bathrooms")),
        "area_sqft": safe_float(row.get("area_sqft")),
        "price": safe_float(row.get("price_inr")),
        "price_per_sqft": safe_float(row.get("price_per_sqft")),
        "furnishing": None,
        "floor": safe_int(row.get("floor_number")),
        "total_floors": safe_int(row.get("total_floors")),
        "property_age": None,
        "parking": safe_int(row.get("parking_spaces")),
        "listing_date": None,
    }

    # Normalize city names
    city = listing.get("city", "")
    if city:
        city = city.strip()
        # Normalize Bangalore -> Bengaluru
        if city.lower() == "bangalore":
            listing["city"] = "Bengaluru"
        else:
            listing["city"] = city.title()

    # Normalize property type
    prop_type = listing.get("property_type", "")
    if prop_type:
        prop_type = prop_type.strip().title()
        if "Apartment" in prop_type or "Flat" in prop_type:
            listing["property_type"] = "Apartment"
        elif "Villa" in prop_type:
            listing["property_type"] = "Villa"
        elif "House" in prop_type or "Independent" in prop_type:
            listing["property_type"] = "Independent House"
        elif "Plot" in prop_type or "Land" in prop_type:
            listing["property_type"] = "Plot"

    # Compute quality score
    quality = compute_quality_score(listing, source_count=1)
    listing["data_quality_score"] = quality["quality_score"]
    listing["quality_completeness"] = quality["completeness"]
    listing["quality_freshness"] = quality["freshness"]
    listing["source_count"] = 1
    listing["imputed_fields"] = quality["imputed_fields"]
    listing["sources"] = [listing.get("source", "unknown")]

    return listing


async def replace_dataset():
    """Clear old data and import new dataset."""
    print("=" * 60)
    print("REPLACING PROPERTY DATASET")
    print("=" * 60)

    # Step 1: Clear existing data
    print("\n[Step 1] Clearing existing data...")
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM property_listings"))
        print("  Cleared all existing rows")

    # Step 2: Read new dataset
    print("\n[Step 2] Reading new dataset...")
    df = pd.read_csv("../india_properties_clean.csv")
    print(f"  Read {len(df)} rows")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Cities: {df['city'].nunique()}")

    # Step 3: Map and import
    print("\n[Step 3] Importing to PostgreSQL...")
    await init_db()

    async with AsyncSessionLocal() as session:
        imported = 0
        skipped = 0
        batch_size = 50

        for idx, (_, row) in enumerate(df.iterrows()):
            try:
                listing = map_listing(row)

                # Skip rows with no locality or no price
                if not listing.get("locality") or not listing.get("price"):
                    skipped += 1
                    continue

                db_listing = PropertyListingDB(
                    source=listing.get("source", "unknown"),
                    source_url=listing.get("source_url"),
                    state=listing.get("state"),
                    city=listing.get("city"),
                    locality=listing.get("locality"),
                    pincode=listing.get("pincode"),
                    property_type=listing.get("property_type"),
                    transaction_type="Sale",
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
                    listing_date=None,
                    data_quality_score=listing.get("data_quality_score", 0.0),
                    quality_completeness=listing.get("quality_completeness", 0.0),
                    quality_freshness=listing.get("quality_freshness", 0.0),
                    source_count=1,
                    imputed_fields=listing.get("imputed_fields", []),
                    sources=listing.get("sources", []),
                )
                session.add(db_listing)
                imported += 1

                # Commit every batch_size rows
                if imported % batch_size == 0:
                    await session.commit()
                    print(f"  Imported {imported} rows...")

            except Exception as exc:
                await session.rollback()
                skipped += 1
                continue

        await session.commit()

    # Step 4: Verify
    print("\n[Step 4] Verifying import...")
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func

        result = await session.execute(
            select(func.count(PropertyListingDB.id))
        )
        total = result.scalar()

        result = await session.execute(
            select(
                PropertyListingDB.city,
                func.count(PropertyListingDB.id),
            ).group_by(PropertyListingDB.city)
        )
        cities = result.all()

        result = await session.execute(
            select(
                func.min(PropertyListingDB.data_quality_score),
                func.max(PropertyListingDB.data_quality_score),
                func.avg(PropertyListingDB.data_quality_score),
            )
        )
        min_q, max_q, avg_q = result.one()

    print(f"\n{'=' * 60}")
    print("REPLACEMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Imported: {imported}")
    print(f"  Skipped: {skipped}")
    print(f"  Total in database: {total}")
    print(f"\n  Cities:")
    for city, count in cities:
        print(f"    {city}: {count}")
    print(f"\n  Quality scores:")
    print(f"    Min: {min_q}")
    print(f"    Max: {max_q}")
    print(f"    Avg: {avg_q:.1f}")


if __name__ == "__main__":
    asyncio.run(replace_dataset())
