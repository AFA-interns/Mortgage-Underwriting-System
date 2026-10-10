"""
Fuzzy property matching across multiple data sources.

Matches listings from different websites that refer to the same
property, so we can merge their data and fill NULLs.
"""

from __future__ import annotations

import re
from typing import Any


def normalize_text(text: str | None) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def compute_match_score(
    a: dict[str, Any],
    b: dict[str, Any],
) -> float:
    """
    Compute match score (0-1) between two listings.

    Uses multiple signals:
    - Locality similarity (50%)
    - Area similarity (25%)
    - Bedroom match (15%)
    - Price similarity (10%)
    """
    scores: list[float] = []
    weights: list[float] = []

    # Locality (50%) — most important for matching
    loc_a = normalize_text(a.get("locality"))
    loc_b = normalize_text(b.get("locality"))
    if loc_a and loc_b:
        if loc_a == loc_b:
            scores.append(1.0)
        elif loc_a in loc_b or loc_b in loc_a:
            scores.append(0.7)
        else:
            # Word overlap
            words_a = set(loc_a.split())
            words_b = set(loc_b.split())
            if words_a and words_b:
                overlap = len(words_a & words_b) / max(
                    len(words_a), len(words_b)
                )
                scores.append(overlap * 0.3)
            else:
                scores.append(0.0)
        weights.append(0.50)

    # Area (25%)
    area_a = a.get("area_sqft")
    area_b = b.get("area_sqft")
    if area_a and area_b and area_a > 0 and area_b > 0:
        ratio = min(area_a, area_b) / max(area_a, area_b)
        scores.append(ratio)
        weights.append(0.25)

    # Bedrooms (15%)
    bed_a = a.get("bedrooms")
    bed_b = b.get("bedrooms")
    if bed_a is not None and bed_b is not None:
        if bed_a == bed_b:
            scores.append(1.0)
        elif abs(bed_a - bed_b) == 1:
            scores.append(0.3)
        else:
            scores.append(0.0)
        weights.append(0.15)

    # Price (10%)
    price_a = a.get("price")
    price_b = b.get("price")
    if price_a and price_b and price_a > 0 and price_b > 0:
        ratio = min(price_a, price_b) / max(price_a, price_b)
        scores.append(ratio)
        weights.append(0.10)

    if not scores:
        return 0.0

    # Weighted average
    total_weight = sum(weights)
    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    base_score = weighted_sum / total_weight

    # Apply penalty for critical mismatches
    penalty = 1.0

    # BHK mismatch penalty
    if bed_a is not None and bed_b is not None and bed_a != bed_b:
        penalty *= 0.5

    # Locality mismatch penalty
    if loc_a and loc_b and loc_a != loc_b:
        penalty *= 0.6

    return round(base_score * penalty, 3)


def match_listings(
    listings_a: list[dict[str, Any]],
    listings_b: list[dict[str, Any]],
    threshold: float = 0.6,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """
    Match listings from source A to source B.

    Returns list of (a, b, score) tuples for matches above threshold.
    Each listing can only be matched once (greedy best-match).
    """
    matches: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    used_b: set[int] = set()

    # Sort by best possible match (greedy)
    candidates: list[tuple[float, int, int]] = []
    for i, a in enumerate(listings_a):
        for j, b in enumerate(listings_b):
            score = compute_match_score(a, b)
            if score >= threshold:
                candidates.append((score, i, j))

    # Sort descending by score
    candidates.sort(reverse=True)

    used_a: set[int] = set()
    for score, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        matches.append((listings_a[i], listings_b[j], score))
        used_a.add(i)
        used_b.add(j)

    return matches
