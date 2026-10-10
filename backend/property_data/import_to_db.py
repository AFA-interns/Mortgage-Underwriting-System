"""
Import enriched CSV data to PostgreSQL.

Usage:
    python -m property_data.import_to_db
"""

import asyncio
import json

import pandas as pd
from sqlalchemy import select

from property_data.database.connection import AsyncSessionLocal, init_db
from property_data.database.models import PropertyListingDB


async def main():
    # Initialize database tables
    await init_db()

    # Read enriched CSV
    df = pd.read_csv("data/enriched_properties.csv")

    print(f"Importing {len(df)} rows to PostgreSQL...")

    async with AsyncSessionLocal() as session:
        imported = 0
        skipped = 0

        for _, row in df.iterrows():
            # Check if already exists
            locality = row.get("locality")
            city = row.get("city")
            bedrooms = row.get("bedrooms")
            area_sqft = row.get("area_sqft")

            result = await session.execute(
                select(PropertyListingDB).where(
                    PropertyListingDB.city == city,
                    PropertyListingDB.locality == locality,
                    PropertyListingDB.bedrooms == bedrooms,
                    PropertyListingDB.area_sqft == area_sqft,
                )
            )

            if result.scalar_one_or_none():
                skipped += 1
                continue

            # Parse imputed_fields from CSV string
            imputed_str = row.get("imputed_fields", "")
            imputed_fields = (
                [f.strip() for f in imputed_str.split(",") if f.strip()]
                if imputed_str
                else []
            )

            # Create new record
            db_listing = PropertyListingDB(
                source=row.get("source", "csv_import"),
                source_url=None,
                state="Karnataka",
                city=city,
                locality=locality,
                pincode=str(row.get("pincode")) if pd.notna(row.get("pincode")) else None,
                property_type=row.get("property_type"),
                transaction_type="Sale",
                bedrooms=int(bedrooms) if pd.notna(bedrooms) else None,
                bathrooms=int(row.get("bathrooms")) if pd.notna(row.get("bathrooms")) else None,
                area_sqft=float(area_sqft) if pd.notna(area_sqft) else None,
                price=float(row.get("price_inr")) if pd.notna(row.get("price_inr")) else None,
                price_per_sqft=float(row.get("price_per_sqft")) if pd.notna(row.get("price_per_sqft")) else None,
                furnishing=row.get("furnishing"),
                floor=int(row.get("floor")) if pd.notna(row.get("floor")) else None,
                total_floors=int(row.get("total_floors")) if pd.notna(row.get("total_floors")) else None,
                property_age=int(row.get("property_age")) if pd.notna(row.get("property_age")) else None,
                parking=int(row.get("parking")) if pd.notna(row.get("parking")) else None,
                listing_date=None,
                data_quality_score=float(row.get("data_quality_score", 0)) if pd.notna(row.get("data_quality_score")) else 0.0,
                quality_completeness=0.0,
                quality_freshness=50.0,
                source_count=1,
                imputed_fields=imputed_fields,
                sources=["csv_import"],
            )

            session.add(db_listing)
            imported += 1

        await session.commit()

    print(f"\nImport complete!")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Total in database: {imported + skipped}")


if __name__ == "__main__":
    asyncio.run(main())
