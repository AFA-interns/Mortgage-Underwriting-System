@'
import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.database.connection import AsyncSessionLocal
from property_data.database.repository import find_comparables


async def main():

    async with AsyncSessionLocal() as session:

        properties = await find_comparables(
            session,
            city="Bangalore",
            locality="Whitefield",
            bedrooms=2,
        )

        print(f"COMPARABLES FOUND: {len(properties)}")

        for property_obj in properties:
            print(
                f"ID={property_obj.id} | "
                f"{property_obj.bedrooms} BHK | "
                f"{property_obj.area_sqft} sqft | "
                f"₹{property_obj.price} | "
                f"₹{property_obj.price_per_sqft}/sqft"
            )


if __name__ == "__main__":
    asyncio.run(main())
'@ | Set-Content ".\backend\property_data\test_comparables.py"