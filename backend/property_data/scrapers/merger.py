"""
Multi-source property data merger.

Combines listings from multiple sources, matches them,
fills NULLs, and computes quality scores.
"""

from __future__ import annotations

import re
from typing import Any

from property_data.scrapers.matcher import match_listings
from property_data.scrapers.quality import compute_quality_score


# Fields to merge (fill NULLs from other sources)
MERGEABLE_FIELDS = [
    "locality",
    "pincode",
    "bathrooms",
    "furnishing",
    "floor",
    "total_floors",
    "property_age",
    "parking",
    "price",
    "price_per_sqft",
    "area_sqft",
    "bedrooms",
    "property_type",
]


def merge_sources(
    sources: dict[str, list[dict[str, Any]]],
    match_threshold: float = 0.6,
    threshold: float | None = None,
) -> list[dict[str, Any]]:
    """
    Merge listings from multiple sources.

    Args:
        sources: Dict mapping source name to list of listings
        match_threshold: Minimum match score to consider two listings as same property

    Returns:
        List of merged listings with quality scores
    """
    if not sources:
        return []

    # Support both parameter names for backward compatibility
    if threshold is not None:
        match_threshold = threshold

    # Get the primary source (most listings)
    primary_source = max(sources.keys(), key=lambda k: len(sources[k]))
    primary_listings = sources[primary_source]

    # Start with primary listings
    merged: list[dict[str, Any]] = []
    for listing in primary_listings:
        merged_listing = dict(listing)
        merged_listing["sources"] = [primary_source]
        merged_listing["source_count"] = 1
        merged_listing["imputed_fields"] = []
        merged.append(merged_listing)

    # Merge each additional source
    for source_name, source_listings in sources.items():
        if source_name == primary_source:
            continue

        # Match listings from this source to merged listings
        matches = match_listings(merged, source_listings, threshold=match_threshold)

        for merged_listing, source_listing, score in matches:
            # Fill NULLs from source
            for field in MERGEABLE_FIELDS:
                if _is_empty(merged_listing.get(field)) and not _is_empty(
                    source_listing.get(field)
                ):
                    merged_listing[field] = source_listing[field]
                    if field not in merged_listing["imputed_fields"]:
                        merged_listing["imputed_fields"].append(field)

            # Add source to list
            if source_name not in merged_listing["sources"]:
                merged_listing["sources"].append(source_name)
                merged_listing["source_count"] += 1

        # Add unmatched listings from this source
        matched_urls = {id(m[1]) for m in matches}
        for source_listing in source_listings:
            if id(source_listing) not in matched_urls:
                new_listing = dict(source_listing)
                new_listing["sources"] = [source_name]
                new_listing["source_count"] = 1
                new_listing["imputed_fields"] = []
                merged.append(new_listing)

    # Compute quality scores
    for listing in merged:
        quality = compute_quality_score(
            listing,
            source_count=listing.get("source_count", 1),
        )
        listing["data_quality_score"] = quality["quality_score"]
        listing["quality_completeness"] = quality["completeness"]
        listing["quality_freshness"] = quality["freshness"]

    # Sort by quality score descending
    merged.sort(key=lambda x: x.get("data_quality_score", 0), reverse=True)

    return merged


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False


def merge_two_listings(
    base: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge two listings, filling NULLs in base with values from overlay.

    Returns a new merged listing.
    """
    merged = dict(base)
    imputed = list(base.get("imputed_fields", []))

    for field in MERGEABLE_FIELDS:
        if _is_empty(merged.get(field)) and not _is_empty(overlay.get(field)):
            merged[field] = overlay[field]
            if field not in imputed:
                imputed.append(field)

    merged["imputed_fields"] = imputed

    # Merge sources
    base_sources = set(base.get("sources", [base.get("source", "")]))
    overlay_sources = set(overlay.get("sources", [overlay.get("source", "")]))
    merged["sources"] = list(base_sources | overlay_sources)
    merged["source_count"] = len(merged["sources"])

    return merged
