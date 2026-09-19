import httpx
from typing import Any


AVNESTER_URL = "https://api.avnester.com/public/v1/search_properties"


async def search_properties(filters: dict[str, Any]) -> dict[str, Any]:
    """Call AVnester property search API."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            AVNESTER_URL,
            json=filters,
        )

        response.raise_for_status()
        return response.json()