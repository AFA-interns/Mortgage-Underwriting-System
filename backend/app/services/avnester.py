from __future__ import annotations

from typing import Any

import httpx


AVNESTER_URL = (
    "https://api.avnester.com/public/v1/search_properties"
)


def search_properties(
    filters: dict[str, Any],
) -> dict[str, Any]:
    """
    Search property listings using the AVnester public API.
    """

    with httpx.Client(timeout=30.0) as client:

        response = client.post(
            AVNESTER_URL,
            json=filters,
        )

        response.raise_for_status()

        return response.json()