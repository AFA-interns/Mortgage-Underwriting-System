"""
Add quality tracking columns to property_listings table.

Run this once after updating the model:
    python -m property_data.migrate_add_quality_columns
"""

import asyncio

from property_data.database.connection import engine


async def migrate():
    async with engine.begin() as conn:
        # Check which columns exist
        from sqlalchemy import text

        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'property_listings'"
            )
        )
        existing_columns = {row[0] for row in result}

        print(f"Existing columns: {sorted(existing_columns)}")

        # Columns to add
        columns_to_add = {
            "data_quality_score": "FLOAT DEFAULT 0.0",
            "quality_completeness": "FLOAT DEFAULT 0.0",
            "quality_freshness": "FLOAT DEFAULT 0.0",
            "source_count": "INTEGER DEFAULT 1",
            "imputed_fields": "JSON DEFAULT '[]'",
            "sources": "JSON DEFAULT '[]'",
        }

        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                print(f"  Adding column: {col_name}")
                await conn.execute(
                    text(
                        f"ALTER TABLE property_listings "
                        f"ADD COLUMN {col_name} {col_type}"
                    )
                )
            else:
                print(f"  Column already exists: {col_name}")

        # Add indexes for faster comps lookup
        index_queries = [
            (
                "idx_property_listings_city",
                "CREATE INDEX IF NOT EXISTS idx_property_listings_city "
                "ON property_listings (city)",
            ),
            (
                "idx_property_listings_locality",
                "CREATE INDEX IF NOT EXISTS idx_property_listings_locality "
                "ON property_listings (locality)",
            ),
            (
                "idx_property_listings_city_locality",
                "CREATE INDEX IF NOT EXISTS idx_property_listings_city_locality "
                "ON property_listings (city, locality)",
            ),
        ]

        for idx_name, idx_query in index_queries:
            print(f"  Creating index: {idx_name}")
            await conn.execute(text(idx_query))

        print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
