from __future__ import annotations

from typing import Any

import httpx


AVNESTER_URL = "https://api.avnester.com/public/v1/search_properties"


async def search_properties(
    filters: dict[str, Any],
) -> dict[str, Any]:
    """
    Search property listings using the AVnester public API.

    Args:
        filters: Property search filters expected by AVnester.

    Returns:
        JSON response returned by the AVnester API.

    Raises:
        httpx.HTTPStatusError: If AVnester returns a non-2xx response.
        httpx.RequestError: If the request cannot reach AVnester.
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            AVNESTER_URL,
            json=filters,
        )

        response.raise_for_status()

        return response.json()