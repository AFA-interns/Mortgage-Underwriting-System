import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB


async def main():
    async with AsyncSessionLocal() as session:

        property_data = PropertyListingDB(
            source="demo_source",
            source_url="https://example.com/property/123",
            state="Karnataka",
            city="Bangalore",
            locality="Whitefield",
            pincode="560066",
            property_type="Apartment",
            transaction_type="Sale",
            bedrooms=2,
            bathrooms=2,
            area_sqft=1200,
            price=6500000,
            price_per_sqft=5416.67,
            furnishing="Semi-Furnished",
            floor=5,
            total_floors=10,
            property_age=5,
            parking=1,
        )

        session.add(property_data)
        await session.commit()

        print("PROPERTY INSERTED SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(main())