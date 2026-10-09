"""
Free geocoding using Nominatim (OpenStreetMap).

No API key required. Rate limit: 1 request per second.

Usage:
    from property_data.geocoder import geocode_locality, reverse_geocode
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# Required by Nominatim usage policy
USER_AGENT = "MortgageUnderwritingSystem/1.0 (educational project)"


async def geocode_locality(
    locality: str,
    city: str,
    state: str | None = None,
) -> dict[str, Any] | None:
    """
    Geocode a locality name to get lat/long and pincode.

    Args:
        locality: Locality name (e.g., "Whitefield")
        city: City name (e.g., "Bangalore")
        state: Optional state name

    Returns:
        Dict with lat, lon, pincode, display_name or None
    """
    query = f"{locality}, {city}"
    if state:
        query += f", {state}"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()

            if not results:
                return None

            result = results[0]
            address = result.get("address", {})

            # Extract pincode from address
            pincode = address.get("postcode")

            return {
                "lat": float(result.get("lat", 0)),
                "lon": float(result.get("lon", 0)),
                "pincode": pincode,
                "display_name": result.get("display_name"),
                "locality": locality,
                "city": city,
                "state": state,
            }

        except Exception as exc:
            print(f"[GEOCODER] Failed to geocode {query}: {exc}")
            return None


async def reverse_geocode(
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    """
    Reverse geocode lat/long to get address and pincode.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dict with address details or None
    """
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
    }

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(REVERSE_URL, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

            address = result.get("address", {})

            return {
                "pincode": address.get("postcode"),
                "locality": address.get("suburb") or address.get("neighbourhood"),
                "city": address.get("city") or address.get("town"),
                "state": address.get("state"),
                "display_name": result.get("display_name"),
            }

        except Exception as exc:
            print(f"[GEOCODER] Failed to reverse geocode: {exc}")
            return None


async def enrich_listings_with_geocoding(
    listings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Enrich listings with geocoded pincodes.

    For each listing with a locality but no pincode,
    geocode to get the pincode.

    Args:
        listings: List of property listing dicts

    Returns:
        Enriched listings with pincodes filled
    """
    enriched = []

    for listing in listings:
        enriched_listing = dict(listing)

        # If pincode is missing, try to geocode
        if not enriched_listing.get("pincode"):
            locality = enriched_listing.get("locality")
            city = enriched_listing.get("city")

            if locality and city:
                result = await geocode_locality(locality, city)

                if result and result.get("pincode"):
                    enriched_listing["pincode"] = result["pincode"]
                    enriched_listing["geo_lat"] = result["lat"]
                    enriched_listing["geo_lon"] = result["lon"]

                    if "pincode" not in enriched_listing.get("imputed_fields", []):
                        enriched_listing.setdefault("imputed_fields", []).append("pincode")

        enriched.append(enriched_listing)

        # Respect Nominatim rate limit (1 req/sec)
        await asyncio.sleep(1.1)

    return enriched


# Synchronous wrapper for convenience
def geocode_locality_sync(
    locality: str,
    city: str,
    state: str | None = None,
) -> dict[str, Any] | None:
    """Synchronous wrapper for geocode_locality."""
    return asyncio.run(geocode_locality(locality, city, state))


def reverse_geocode_sync(
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    """Synchronous wrapper for reverse_geocode."""
    return asyncio.run(reverse_geocode(lat, lon))
