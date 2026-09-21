from __future__ import annotations

from typing import Any

from app.services.avnester import search_properties


def fetch_api_valuation(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
) -> dict[str, Any]:
    """
    Fetch property listings from AVnester and use
    their price-per-square-foot values to estimate
    the subject property's market value.
    """

    # ---------------------------------------------------------
    # Normalize property type for AVnester
    # ---------------------------------------------------------
    property_type_lower = str(property_type).lower()

    if (
        "apartment" in property_type_lower
        or "flat" in property_type_lower
        or "residential" in property_type_lower
    ):
        avnester_property_type = "apartment"
    else:
        avnester_property_type = property_type_lower

    # ---------------------------------------------------------
    # Build AVnester request
    # ---------------------------------------------------------
    filters = {
        "city": city,
        "localityName": locality,
        "propertyType": avnester_property_type,
        "bhk": bhk,
        "transactionType": "sale",
        "limit": 5,
    }

    print("\n[AVNESTER REQUEST]")
    print(filters)

    # ---------------------------------------------------------
    # Call AVnester
    # ---------------------------------------------------------
    response = search_properties(filters)

    # ---------------------------------------------------------
    # Read response
    # ---------------------------------------------------------
    listings = response.get("listings", [])

    valid_listings = []

    # ---------------------------------------------------------
    # Extract usable listings
    # ---------------------------------------------------------
    for listing in listings:

        price = listing.get("price")
        area = listing.get("areaSqft")

        if price and area and area > 0:

            price_per_sqft = price / area

            valid_listings.append(
                {
                    "listing_id": listing.get("listingId"),
                    "title": listing.get("title"),
                    "price_inr": price,
                    "area_sqft": area,
                    "bhk": listing.get("bhk"),
                    "rera_id": listing.get("reraId"),
                    "price_per_sqft_inr": price_per_sqft,
                }
            )

    # ---------------------------------------------------------
    # No usable listings
    # ---------------------------------------------------------
    if not valid_listings:

        return {
            "api_name": "AVnester",
            "estimated_market_value_inr": 0,
            "price_per_sqft_inr": 0,
            "valuation_range_inr": {
                "low": 0,
                "high": 0,
            },
            "api_confidence_score": 0,
            "comparables": [],
        }

    # ---------------------------------------------------------
    # Calculate average price per square foot
    # ---------------------------------------------------------
    average_price_per_sqft = (
        sum(
            item["price_per_sqft_inr"]
            for item in valid_listings
        )
        / len(valid_listings)
    )

    # ---------------------------------------------------------
    # Estimate subject property value
    # ---------------------------------------------------------
    estimated_value = (
        average_price_per_sqft * area_sqft
    )

    # ---------------------------------------------------------
    # Confidence based on number of listings
    # ---------------------------------------------------------
    api_confidence_score = min(
        0.90,
        0.50 + (0.10 * len(valid_listings)),
    )

    # ---------------------------------------------------------
    # Return valuation result
    # ---------------------------------------------------------
    return {
        "api_name": "AVnester",

        "estimated_market_value_inr": estimated_value,

        "price_per_sqft_inr": average_price_per_sqft,

        "valuation_range_inr": {
            "low": estimated_value * 0.90,
            "high": estimated_value * 1.10,
        },

        "api_confidence_score": api_confidence_score,

        "comparables": valid_listings,
    }