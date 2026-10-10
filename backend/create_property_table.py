import asyncio
import sys
sys.path.insert(0, "backend")
from property_data.database.connection import init_db
async def main():
    await init_db()
    print("PROPERTY TABLE CREATED SUCCESSFULLY")
if __name__ == "__main__":
    asyncio.run(main())
