from __future__ import annotations

import logging
import statistics
from typing import Any

from app.services.avnester import search_properties

logger = logging.getLogger(__name__)

_MIN_LOCALITY_COMPS = 3
_MAX_LIMIT = 20  # AVnester rejects limit > 20


def _avnester_property_type(property_type: str) -> str | None:
    """Maps free-text types onto AVnester's enum:
    apartment | villa | plot | independent_house."""
    t = str(property_type).lower()
    if "plot" in t or "land" in t:
        return "plot"
    if "villa" in t:
        return "villa"
    if "house" in t:
        return "independent_house"
    if "apartment" in t or "flat" in t or "residential" in t:
        return "apartment"
    return None


def _usable(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalises AVnester listings, dropping those without price or area."""
    out = []
    for item in listings:
        price = item.get("price")
        area = item.get("carpetAreaSqft") or item.get("areaSqft")
        if not price or not area or area <= 0:
            continue
        out.append(
            {
                "listing_id": item.get("listingId"),
                "title": item.get("title"),
                "locality": item.get("locality"),
                "price_inr": price,
                "area_sqft": area,
                "bhk": item.get("bhk"),
                "rera_id": item.get("reraId"),
                "price_per_sqft_inr": price / area,
                "source_url": item.get("sourceUrl"),
            }
        )
    return out


def _search(filters: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        response = search_properties(filters)
    except Exception as exc:  # network error, timeout, non-2xx, bad JSON
        logger.warning("AVnester call failed: %s", exc)
        return []
    return _usable(response.get("listings", []))


def _empty() -> dict[str, Any]:
    return {
        "api_name": "AVnester",
        "estimated_market_value_inr": 0,
        "price_per_sqft_inr": 0,
        "valuation_range_inr": {"low": 0, "high": 0},
        "api_confidence_score": 0,
        "comparables": [],
        "scope": None,
    }


def fetch_api_valuation(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
) -> dict[str, Any]:
    """Estimates market value from live AVnester for-sale listings.

    Searches the subject's locality first and widens to the whole city when
    fewer than three usable comparables exist. Uses the median price per
    sq ft (robust to outlier listings) times the subject's area.
    """
    avn_type = _avnester_property_type(property_type)
    base: dict[str, Any] = {
        "city": city,
        "transactionType": "sale",
        "limit": _MAX_LIMIT,
    }
    if avn_type:
        base["propertyType"] = avn_type

    scope = "locality"
    listings = _search({**base, "locality": locality}) if locality else []
    if len(listings) < _MIN_LOCALITY_COMPS:
        scope = "city"
        listings = _search(base)

    if not listings or not area_sqft or area_sqft <= 0:
        return _empty()

    median_ppsf = statistics.median(i["price_per_sqft_inr"] for i in listings)
    estimated = median_ppsf * area_sqft

    confidence = min(0.90, 0.50 + 0.10 * len(listings))
    if scope == "city":
        confidence -= 0.10  # comparables are not from the subject's locality

    return {
        "api_name": "AVnester",
        "estimated_market_value_inr": estimated,
        "price_per_sqft_inr": median_ppsf,
        "measurement_basis": "carpet_area",
        "valuation_range_inr": {"low": estimated * 0.90, "high": estimated * 1.10},
        "api_confidence_score": round(confidence, 2),
        "comparables": listings,
        "scope": scope,
    }
