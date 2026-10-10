"""
Data quality scoring for property listings.

Scores each record 0-100 based on:
- Completeness (how many critical fields are filled)
- Source diversity (how many sources agree)
- Freshness (how recent the listing is)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


# Critical fields for comps analysis and their weights
CRITICAL_FIELDS: dict[str, float] = {
    "locality": 20.0,
    "price": 20.0,
    "area_sqft": 15.0,
    "bedrooms": 10.0,
    "bathrooms": 5.0,
    "furnishing": 5.0,
    "floor": 5.0,
    "total_floors": 5.0,
    "property_age": 5.0,
    "parking": 5.0,
    "pincode": 5.0,
}

# All fields that contribute to completeness
ALL_FIELDS = list(CRITICAL_FIELDS.keys())


def compute_completeness(listing: dict[str, Any]) -> float:
    """
    Compute completeness score (0-100) based on filled critical fields.
    """
    if not listing:
        return 0.0

    total_weight = sum(CRITICAL_FIELDS.values())
    earned_weight = 0.0

    for field, weight in CRITICAL_FIELDS.items():
        value = listing.get(field)
        if value is not None and value != "" and value != 0:
            earned_weight += weight

    return round((earned_weight / total_weight) * 100, 1)


def compute_freshness(listing: dict[str, Any]) -> float:
    """
    Compute freshness score (0-100) based on listing age.
    """
    listing_date = listing.get("listing_date")
    if not listing_date:
        return 50.0  # Unknown freshness — neutral

    if isinstance(listing_date, str):
        try:
            listing_date = datetime.fromisoformat(
                listing_date.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return 50.0

    if isinstance(listing_date, datetime):
        age_days = (datetime.utcnow() - listing_date).days
        if age_days <= 7:
            return 100.0
        if age_days <= 30:
            return 90.0
        if age_days <= 60:
            return 70.0
        if age_days <= 90:
            return 50.0
        if age_days <= 180:
            return 30.0
        return 10.0

    return 50.0


def compute_quality_score(
    listing: dict[str, Any],
    source_count: int = 1,
) -> dict[str, Any]:
    """
    Compute overall quality score for a listing.

    Returns dict with:
    - quality_score: 0-100 overall
    - completeness: 0-100 field completeness
    - freshness: 0-100 listing recency
    - source_count: number of sources
    - imputed_fields: list of fields that were imputed
    """
    completeness = compute_completeness(listing)
    freshness = compute_freshness(listing)

    # Source diversity bonus (max 30 points for 3+ sources)
    source_bonus = min(source_count * 10, 30)

    # Weighted combination — completeness dominates
    quality = (
        completeness * 0.70
        + freshness * 0.10
        + source_bonus
    )

    # Penalty for imputed fields
    imputed = listing.get("imputed_fields", [])
    imputation_penalty = len(imputed) * 2

    final_score = max(0, min(100, round(quality - imputation_penalty, 1)))

    return {
        "quality_score": final_score,
        "completeness": completeness,
        "freshness": freshness,
        "source_count": source_count,
        "imputed_fields": imputed,
    }


def get_quality_label(score: float) -> str:
    """Convert numeric score to human-readable label."""
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "fair"
    if score >= 20:
        return "poor"
    return "unusable"
