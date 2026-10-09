"""
Data enrichment pipeline for property listings.

Fills NULL values in scraped data using:
1. Geocoding (locality -> pincode)
2. Property type inference (bathrooms, furnishing, etc.)
3. Cross-source data merging
4. Statistical imputation
"""

from __future__ import annotations

import re
from typing import Any

from property_data.scrapers.quality import compute_quality_score


# Typical bathrooms by BHK
BATHROOMS_BY_BHK: dict[int, int] = {
    1: 1,
    2: 2,
    3: 2,
    4: 3,
    5: 4,
}

# Typical furnishing by property type
FURNISHING_BY_TYPE: dict[str, str] = {
    "Apartment": "Unfurnished",
    "Villa": "Semi-Furnished",
    "Independent House": "Unfurnished",
    "Plot": "Unfurnished",
}

# Typical parking by property type
PARKING_BY_TYPE: dict[str, int] = {
    "Apartment": 1,
    "Villa": 2,
    "Independent House": 2,
    "Plot": 0,
}

# Typical total floors by property type
TOTAL_FLOORS_BY_TYPE: dict[str, int] = {
    "Apartment": 10,
    "Villa": 2,
    "Independent House": 2,
    "Plot": 1,
}


def enrich_listing(listing: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich a single listing by filling NULL values.

    Returns a new dict with enriched data and quality score.
    """
    enriched = dict(listing)
    imputed: list[str] = []

    # Fill bathrooms based on BHK
    if _is_empty(enriched.get("bathrooms")):
        bhk = enriched.get("bedrooms")
        if bhk and bhk in BATHROOMS_BY_BHK:
            enriched["bathrooms"] = BATHROOMS_BY_BHK[bhk]
            imputed.append("bathrooms")

    # Fill furnishing based on property type
    if _is_empty(enriched.get("furnishing")):
        prop_type = enriched.get("property_type", "")
        furnishing = FURNISHING_BY_TYPE.get(prop_type)
        if furnishing:
            enriched["furnishing"] = furnishing
            imputed.append("furnishing")

    # Fill parking based on property type
    if _is_empty(enriched.get("parking")):
        prop_type = enriched.get("property_type", "")
        parking = PARKING_BY_TYPE.get(prop_type)
        if parking is not None:
            enriched["parking"] = parking
            imputed.append("parking")

    # Fill total floors based on property type
    if _is_empty(enriched.get("total_floors")):
        prop_type = enriched.get("property_type", "")
        total_floors = TOTAL_FLOORS_BY_TYPE.get(prop_type)
        if total_floors:
            enriched["total_floors"] = total_floors
            imputed.append("total_floors")

    # Fill floor (assume middle floor)
    if _is_empty(enriched.get("floor")):
        total = enriched.get("total_floors")
        if total and total > 0:
            enriched["floor"] = total // 2
            imputed.append("floor")

    # Fill property age (assume 5 years if unknown)
    if _is_empty(enriched.get("property_age")):
        enriched["property_age"] = 5
        imputed.append("property_age")

    # Fill pincode from locality (basic mapping for Bangalore)
    if _is_empty(enriched.get("pincode")):
        locality = enriched.get("locality", "")
        pincode = _lookup_pincode(locality)
        if pincode:
            enriched["pincode"] = pincode
            imputed.append("pincode")

    # Compute quality score
    quality = compute_quality_score(enriched, source_count=1)
    enriched["data_quality_score"] = quality["quality_score"]
    enriched["quality_completeness"] = quality["completeness"]
    enriched["quality_freshness"] = quality["freshness"]
    enriched["imputed_fields"] = imputed

    return enriched


def enrich_listings(
    listings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Enrich a list of listings.

    Returns a new list with all listings enriched and sorted by quality.
    """
    enriched = [enrich_listing(listing) for listing in listings]
    enriched.sort(
        key=lambda x: x.get("data_quality_score", 0),
        reverse=True,
    )
    return enriched


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False


def _lookup_pincode(locality: str) -> str | None:
    """
    Basic pincode lookup for common localities.
    In production, use a geocoding API.
    """
    # Bangalore pincodes
    bangalore_pincodes = {
        "whitefield": "560066",
        "indiranagar": "560038",
        "koramangala": "560034",
        "hsr layout": "560102",
        "electronic city": "560100",
        "btm layout": "560076",
        "jayanagar": "560041",
        "malleshwaram": "560003",
        "rajajinagar": "560010",
        "hebbal": "560024",
        "yelahanka": "560064",
        "marathahalli": "560037",
        "sarjapur": "560035",
        "bannerghatta": "560083",
        "devanahalli": "562110",
        "bagalur": "562149",
        "hoskote": "562114",
        "thanisandra": "560077",
        "mathikere": "560054",
        "yeshwanthpur": "560022",
        "vijayanagar": "560040",
        "j.p. nagar": "560078",
        "frazer town": "560005",
        "richmond town": "560025",
        "shivajinagar": "560001",
        "mg road": "560001",
        "residency road": "560025",
        "langford road": "560025",
        "richmond road": "560025",
        "lavelle road": "560001",
        "infantry road": "560001",
        "commercial street": "560001",
        "majestic": "560023",
        "kr market": "560002",
        "yeshwanthpur": "560022",
        "peenya": "560058",
        "rajajinagar": "560010",
        "basaveshwaranagar": "560079",
        "vijayanagar": "560040",
        "nagarbhavi": "560072",
        "mysore road": "560026",
        "kengeri": "560060",
        "uttarahalli": "560061",
        "chamarajpet": "560018",
        "chickpet": "560053",
        "gandhinagar": "560009",
        "shivajinagar": "560001",
        "frazer town": "560005",
        "richmond town": "560025",
        "cox town": "560005",
        "sanjay nagar": "560094",
        "hebbal": "560024",
        "yelahanka": "560064",
        "kr puram": "560036",
        "marathahalli": "560037",
        "sarjapur": "560035",
        "bannerghatta": "560083",
        "electronic city": "560100",
        "hosur road": "560100",
        "jigani": "560105",
        "anekal": "562106",
        "tumkur road": "562106",
        "mysore road": "560026",
        "kanakapura road": "560062",
        "bannerghatta road": "560083",
        "hosur road": "560100",
        "jigani": "560105",
        "anekal": "562106",
        "tumkur road": "562106",
        "mysore road": "560026",
        "kanakapura road": "560062",
    }

    locality_lower = locality.lower().strip()
    return bangalore_pincodes.get(locality_lower)
