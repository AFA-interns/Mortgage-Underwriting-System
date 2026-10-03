import asyncio
import sys

sys.path.insert(0, "backend")

from sqlalchemy import delete

from property_data.database.connection import AsyncSessionLocal
from property_data.database.models import PropertyListingDB


BAD_IDS = [
    10,
    15,
    17,
    25,
    28,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
]


async def main():

    async with AsyncSessionLocal() as session:

        # Delete previously identified bad records
        result_ids = await session.execute(
            delete(PropertyListingDB).where(
                PropertyListingDB.id.in_(BAD_IDS)
            )
        )

        # Delete demo/test records
        result_demo = await session.execute(
            delete(PropertyListingDB).where(
                PropertyListingDB.source == "demo_source"
            )
        )

        await session.commit()

        print(
            f"DELETED BAD RECORDS: {result_ids.rowcount}"
        )

        print(
            f"DELETED DEMO RECORDS: {result_demo.rowcount}"
        )


if __name__ == "__main__":
    asyncio.run(main())