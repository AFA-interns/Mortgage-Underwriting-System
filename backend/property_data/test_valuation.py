import asyncio
import sys

sys.path.insert(0, "backend")

from property_data.database.connection import AsyncSessionLocal
from property_data.database.repository import find_comparables
from property_data.valuation import estimate_value


async def main():

    async with AsyncSessionLocal() as session:

        comparables = await find_comparables(
            session,
            city="Bangalore",
            locality="Whitefield",
            bedrooms=2,
        )

        result = estimate_value(
            comparables,
            target_area_sqft=1300,
        )

        print("VALUATION RESULT:")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())