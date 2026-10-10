from __future__ import annotations

from typing import Any


from app.graph.state import UnderwritingState
from app.services.llm import explain
from app.tools.geocoder import geocode_address
from app.tools.external_api import fetch_api_valuation
from app.tools.local_comparables import fetch_local_valuation
from app.tools.comparables_db import get_comparables_sync


def _extract_property_data(state: UnderwritingState) -> dict:
    doc_out = state.get("doc_ingestion_output") or {}
    prop_profile = doc_out.get("property_profile") or {}
    borrower = state.get("borrower_profile") or {}

    address = (
        prop_profile.get("property_address", "")
        or borrower.get("address", "")
    )

    city = (
        prop_profile.get("city", "")
        or borrower.get("city", "")
    )

    locality = (
        prop_profile.get("locality", "")
        or borrower.get("locality", "")
    )

    property_type = prop_profile.get(
        "property_type",
        "Apartment"
    )

    area_sqft = (
        prop_profile.get("super_builtup_area_sqft")
        or prop_profile.get("carpet_area_sqft")
        or borrower.get("area_sqft", 1000)
    )

    bhk = borrower.get("bhk", 2)
    age_years = borrower.get("age_years", 0)

    return {
        "address": address,
        "locality": locality,
        "city": city,
        "property_type": property_type,
        "bhk": bhk,
        "area_sqft": area_sqft,
        "area_type": "carpet_area",
        "age_years": age_years,
    }


def property_valuation_node(
    state: UnderwritingState
) -> dict[str, Any]:

    errors: list[dict[str, Any]] = list(
        state.get("errors", [])
    )

    prop = _extract_property_data(state)

    # ---------------------------------------------------------
    # CHECK PROPERTY LOCATION
    # ---------------------------------------------------------

    if not prop.get("locality") and not prop.get("city"):
        errors.append({
            "stage": "property_valuation",
            "message": (
                "No property location data available "
                "from document ingestion"
            ),
        })

        return {
            "property_analysis": {
                "estimated_value": 0,
                "valuation_confidence": 0,
                "flags": [
                    "No property data available"
                ],
            },
            "errors": errors,
        }

    # ---------------------------------------------------------
    # NORMALIZE PROPERTY DATA
    # ---------------------------------------------------------

    locality = prop["locality"].title()
    city = prop["city"].title()
    property_type = prop["property_type"].title()
    bhk = prop["bhk"]
    area_sqft = prop["area_sqft"]

    # ---------------------------------------------------------
    # GEOCODING
    # ---------------------------------------------------------

    location_data = geocode_address(
        prop.get("address", ""),
        locality,
        city,
    )

    # ---------------------------------------------------------
    # SCRAPED COMPARABLES DATABASE (SquareYards/Housing/MagicBricks/...)
    # ---------------------------------------------------------
    # get_comparables() is async (its own DB session); get_comparables_sync()
    # bridges it so this node stays a plain sync graph node like the rest of
    # the shared underwriting pipeline.

    db_comps = get_comparables_sync(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    comp_value = 0.0
    db_price_per_sqft = 0.0
    if db_comps:
        prices_per_sqft = [
            c.get("price_per_sqft_inr") for c in db_comps if c.get("price_per_sqft_inr")
        ]
        if prices_per_sqft and area_sqft:
            db_price_per_sqft = sum(prices_per_sqft) / len(prices_per_sqft)
            comp_value = db_price_per_sqft * area_sqft

    # ---------------------------------------------------------
    # AVNESTER LIVE LISTINGS (comparables + estimate)
    # ---------------------------------------------------------

    api_val = fetch_api_valuation(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    comparables = api_val.get("comparables", [])
    api_est = api_val.get("estimated_market_value_inr", 0)
    scope = api_val.get("scope")
    risk_flags: list[str] = []
    value_source = "avnester"
    difference = 0

    if not api_val.get("supported", True) and api_val.get("scope_message"):
        # AVnester tells us outright when a city/state is out of its
        # coverage area (e.g. it only covers Tamil Nadu) - surface that
        # instead of leaving a bare zero unexplained.
        risk_flags.append(api_val["scope_message"])

    if api_est > 0:
        estimated_value = api_est
        method = ["comparable_sales", "avnester"]
        market_range_low = api_val["valuation_range_inr"]["low"]
        market_range_high = api_val["valuation_range_inr"]["high"]
        price_per_sqft = api_val.get("price_per_sqft_inr", 0)
        confidence_score = api_val.get("api_confidence_score", 0)
        if scope == "city":
            risk_flags.append(
                "Fewer than 3 comparables in the subject locality; "
                "city-wide AVnester listings used."
            )
        if len(comparables) < 2:
            risk_flags.append("Insufficient comparable properties available.")
        if comp_value > 0:
            difference = abs(comp_value - api_est) / api_est
            if difference > 0.25:
                risk_flags.append(
                    "Scraped database comparables disagree with AVnester by more "
                    "than 25%; valuation confidence lowered accordingly."
                )
                confidence_score = max(0.0, confidence_score - 0.15)
        explanation = (
            f"Property valuation estimated at Rs {estimated_value:,.0f} "
            f"(median Rs {price_per_sqft:,.0f}/sqft x {area_sqft:,.0f} sqft) "
            f"from {len(comparables)} live AVnester listings "
            f"({scope}-level)."
        )
    elif comp_value > 0:
        # AVnester has nothing usable - the scraped comparables database
        # (SquareYards/Housing/MagicBricks/...) becomes the estimate.
        value_source = "scraped_db"
        comparables = db_comps
        estimated_value = comp_value
        method = ["comparable_sales", "scraped_db"]
        market_range_low = comp_value * 0.90
        market_range_high = comp_value * 1.10
        price_per_sqft = db_price_per_sqft
        confidence_score = 0.70
        risk_flags.append(
            "AVnester returned no usable listings; valuation uses the "
            "scraped property comparables database instead."
        )
        explanation = (
            f"Property valuation estimated at Rs {estimated_value:,.0f} "
            f"(average Rs {price_per_sqft:,.0f}/sqft x {area_sqft:,.0f} sqft) "
            f"from {len(comparables)} scraped comparable listings."
        )
    else:
        # Both the scraped database and AVnester came up empty - fall back
        # to the simpler locality/city median lookup before giving up.
        local_val = fetch_local_valuation(
            locality=locality, city=city, bhk=bhk, area_sqft=area_sqft,
        )
        local_est = local_val.get("estimated_market_value_inr", 0)

        if local_est > 0:
            value_source = "local_db"
            comparables = local_val["comparables"]
            estimated_value = local_est
            method = ["comparable_sales", "local_database"]
            market_range_low = local_val["valuation_range_inr"]["low"]
            market_range_high = local_val["valuation_range_inr"]["high"]
            price_per_sqft = local_val.get("price_per_sqft_inr", 0)
            confidence_score = 0.65 if local_val.get("scope") == "locality" else 0.55
            risk_flags.append(
                "AVnester and the scraped comparables database both had no "
                "usable listings; valuation uses the local median fallback instead."
            )
            explanation = (
                f"Property valuation estimated at Rs {estimated_value:,.0f} "
                f"(median Rs {price_per_sqft:,.0f}/sqft x {area_sqft:,.0f} sqft) "
                f"from {len(comparables)} locally stored comparable listings "
                f"({local_val.get('scope')}-level)."
            )
        else:
            value_source = "none"
            estimated_value = 0
            method = ["avnester", "scraped_db", "local_database"]
            market_range_low = market_range_high = price_per_sqft = 0
            confidence_score = 0.0
            risk_flags.append(
                "No usable AVnester, scraped database, or local comparables "
                "for this property type and location."
            )
            explanation = (
                "Property valuation could not be determined: AVnester, the "
                "scraped comparables database, and the local comparables "
                "database all had no usable listings for this location."
            )

    # ---------------------------------------------------------
    # EXPLANATION (local LLM, template fallback)
    # ---------------------------------------------------------

    explanation = explain(
        system=(
            "You are a property valuation assistant. Explain the valuation in "
            "2-3 plain sentences using only the figures given. Never give or "
            "imply a loan verdict."
        ),
        prompt="\n".join([
            f"Property: {prop.get('property_type')} in {prop.get('locality')}, {prop.get('city')}, "
            f"{prop.get('area_sqft')} sq ft",
            f"Estimated value: {estimated_value}",
            f"Median price per sq ft: {price_per_sqft}",
            f"Comparable listings used: {len(comparables)} ({scope}-level)",
            f"Valuation confidence: {confidence_score:.2f}",
            f"Risk flags: {risk_flags}",
        ]),
        fallback=explanation,
    )

    # ---------------------------------------------------------
    # FINAL OUTPUT
    # ---------------------------------------------------------

    return {
        "property_analysis": {

            "estimated_value":
                estimated_value,

            "market_range_low":
                market_range_low,

            "market_range_high":
                market_range_high,

            "valuation_confidence":
                confidence_score,

            "price_per_sqft":
                price_per_sqft,

            "comparables":
                comparables,

            "rera_status":
                "UNKNOWN",

            "scope":
                scope,

            "valuation_variance_percent":
                round(
                    difference * 100,
                    2,
                )
                if difference
                else 0,

            "flags":
                risk_flags,

            "evidence": [

                {
                    "agent": "property",
                    "field": "estimated_value",
                    "value": estimated_value,
                    "source": value_source,
                },

                {
                    "agent": "property",
                    "field": "comparable_count",
                    "value": len(comparables),
                    "source": value_source,
                },

            ],

            "explanation":
                explanation,

            "location":
                location_data,

            "method":
                method,

            "sources": [
                "Nominatim Geocoder",
                "AVnester",
                "Scraped comparables database",
                "Local comparables database",
            ],
        },

        "errors":
            errors,
    }
