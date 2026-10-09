"""Local comparable-sales valuation — a second source alongside the live
AVnester API (app.tools.external_api), backed by app.services.property_db
(a PostgreSQL table populated by scraping public listing sites; see
backend/property_data/ and backend/scripts/ingest_squareyards.py).

Shaped to match fetch_api_valuation's return value so property valuation
can reconcile the two symmetrically: searches the subject's locality first
and widens to the whole city when fewer than three usable comparables
exist, same pattern as AVnester. Never raises - an empty/unreachable table
degrades to "no local comparables", not an error.
"""
from __future__ import annotations

import statistics
from typing import Any

from app.services.property_db import find_comparables

_MIN_LOCALITY_COMPS = 3


def _usable(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "listing_id": l.get("source_url") or f"{l.get('source')}-{i}",
            "title": f"{l.get('property_type') or 'Property'} in {l.get('locality') or l.get('city')}",
            "locality": l.get("locality"),
            "price_inr": l["price"],
            "area_sqft": l["area_sqft"],
            "bhk": l.get("bedrooms"),
            "price_per_sqft_inr": l["price_per_sqft"],
            "source_url": l.get("source_url"),
            "source": l.get("source"),
        }
        for i, l in enumerate(listings)
        if l.get("price_per_sqft") and l["price_per_sqft"] > 0
        and l.get("price") and l.get("area_sqft")
    ]


def _empty() -> dict[str, Any]:
    return {
        "source_name": "Local comparables (scraped listings)",
        "estimated_market_value_inr": 0,
        "price_per_sqft_inr": 0,
        "valuation_range_inr": {"low": 0, "high": 0},
        "comparables": [],
        "scope": None,
    }


def fetch_local_valuation(
    locality: str, city: str, bhk: int | None, area_sqft: float
) -> dict[str, Any]:
    """Estimates market value from locally stored comparable listings."""
    scope = "locality"
    listings = _usable(find_comparables(city=city, locality=locality, bedrooms=bhk)) if locality else []
    if len(listings) < _MIN_LOCALITY_COMPS:
        scope = "city"
        listings = _usable(find_comparables(city=city, bedrooms=bhk))

    if not listings or not area_sqft or area_sqft <= 0:
        return _empty()

    median_ppsf = statistics.median(l["price_per_sqft_inr"] for l in listings)
    estimated = median_ppsf * area_sqft
    return {
        "source_name": "Local comparables (scraped listings)",
        "estimated_market_value_inr": estimated,
        "price_per_sqft_inr": median_ppsf,
        "valuation_range_inr": {"low": estimated * 0.90, "high": estimated * 1.10},
        "comparables": listings,
        "scope": scope,
    }
