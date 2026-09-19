from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.graph.state import UnderwritingState
from app.tools.geocoder import geocode_address
from app.tools.comparables_db import get_comparables
from app.tools.external_api import fetch_api_valuation


def _extract_property_data(state: UnderwritingState) -> dict:
    doc_out = state.get("doc_ingestion_output") or {}
    prop_profile = doc_out.get("property_profile") or {}
    borrower = state.get("borrower_profile") or {}

    locality = prop_profile.get("city", "") or borrower.get("locality", "")
    address = prop_profile.get("property_address", "") or borrower.get("address", "")
    city = prop_profile.get("city", "") or borrower.get("city", "")
    property_type = prop_profile.get("property_type", "Apartment")
    area_sqft = prop_profile.get("super_builtup_area_sqft") or prop_profile.get("carpet_area_sqft") or borrower.get("area_sqft", 1000)
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


def property_valuation_node(state: UnderwritingState) -> dict[str, Any]:
    errors: list[dict[str, Any]] = list(state.get("errors", []))

    prop = _extract_property_data(state)

    if not prop.get("locality") and not prop.get("city"):
        errors.append({
            "stage": "property_valuation",
            "message": "No property location data available from document ingestion",
        })
        return {
            "property_analysis": {
                "estimated_value": 0,
                "valuation_confidence": 0,
                "flags": ["No property data available"],
            },
            "errors": errors,
        }

    locality = prop["locality"].title()
    city = prop["city"].title()
    property_type = prop["property_type"].title()
    bhk = prop["bhk"]
    area_sqft = prop["area_sqft"]

    location_data = geocode_address(prop.get("address", ""), locality, city)

    comparables = get_comparables(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    api_val = fetch_api_valuation(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    risk_flags = []
    comp_value = 0
    if comparables:
        comp_value = sum(c["price_inr"] for c in comparables) / len(comparables)
    else:
        risk_flags.append("No comparable sales found in local database.")

    api_est = api_val.get("estimated_market_value_inr", 0)

    difference = 0
    if comp_value > 0 and api_est > 0:
        difference = abs(comp_value - api_est) / api_est
    elif comp_value == 0:
        difference = 1.0

    confidence_score = 0.9 - (difference * 1.5)
    confidence_score = max(0, confidence_score)

    if confidence_score < 0.6 or len(comparables) < 2:
        risk_flags.append("High variance between Comps and Market API, or insufficient data.")

    explanation = "Mock Explanation: Property valued at {} based on API and {} comparables.".format(
        api_est, len(comparables)
    )

    if os.environ.get("GEMINI_API_KEY"):
        try:
            llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")
            prompt = f"""
            You are a Property Valuation Assistant. Explain the valuation concisely.
            Property: {prop}
            API Estimated Value: {api_est}
            Comparables Found: {len(comparables)}
            Confidence: {confidence_score:.2f}
            Risk Flags: {risk_flags}
            """
            response = llm.invoke([HumanMessage(content=prompt)])
            explanation = response.content
        except Exception:
            pass

    return {
        "property_analysis": {
            "estimated_value": api_est,
            "market_range_low": api_val.get("valuation_range_inr", {}).get("low", 0),
            "market_range_high": api_val.get("valuation_range_inr", {}).get("high", 0),
            "valuation_confidence": confidence_score,
            "price_per_sqft": api_val.get("price_per_sqft_inr", 0),
            "comparables": comparables,
            "rera_status": "UNKNOWN",
            "valuation_variance_percent": round(difference * 100, 2) if difference else 0,
            "flags": risk_flags,
            "evidence": [
                {"agent": "property", "field": "estimated_value", "value": api_est, "source": "mock_external_api"},
                {"agent": "property", "field": "comparable_count", "value": len(comparables), "source": "local_db"},
            ],
            "explanation": explanation,
            "location": location_data,
            "method": ["comparable_sales", "mock_external_api"],
            "sources": ["Nominatim Geocoder", "Mock Zapkey AVM", "Local Dummy DB"],
        },
        "errors": errors,
    }
