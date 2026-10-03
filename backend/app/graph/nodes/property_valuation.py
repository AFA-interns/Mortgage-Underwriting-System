from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.graph.state import UnderwritingState
from app.tools.geocoder import geocode_address
from app.tools.comparables_db import get_comparables
from app.tools.external_api import fetch_api_valuation


def _extract_property_data(
    state: UnderwritingState
) -> dict:

    doc_out = state.get(
        "doc_ingestion_output"
    ) or {}

    prop_profile = doc_out.get(
        "property_profile"
    ) or {}

    borrower = state.get(
        "borrower_profile"
    ) or {}

    address = (
        prop_profile.get(
            "property_address",
            ""
        )
        or borrower.get(
            "address",
            ""
        )
    )

    city = (
        prop_profile.get(
            "city",
            ""
        )
        or borrower.get(
            "city",
            ""
        )
    )

    locality = (
        prop_profile.get(
            "locality",
            ""
        )
        or borrower.get(
            "locality",
            ""
        )
    )

    property_type = prop_profile.get(
        "property_type",
        "Apartment"
    )

    area_sqft = (
        prop_profile.get(
            "super_builtup_area_sqft"
        )
        or prop_profile.get(
            "carpet_area_sqft"
        )
        or borrower.get(
            "area_sqft",
            1000
        )
    )

    bhk = borrower.get(
        "bhk",
        2
    )

    age_years = borrower.get(
        "age_years",
        0
    )

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


async def property_valuation_node(
    state: UnderwritingState
) -> dict[str, Any]:

    errors: list[dict[str, Any]] = list(
        state.get(
            "errors",
            []
        )
    )

    prop = _extract_property_data(
        state
    )

    # =========================================================
    # CHECK PROPERTY LOCATION
    # =========================================================

    if (
        not prop.get("locality")
        and not prop.get("city")
    ):

        errors.append(
            {
                "stage": "property_valuation",
                "message": (
                    "No property location data "
                    "available from document ingestion"
                ),
            }
        )

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

    # =========================================================
    # NORMALIZE PROPERTY DATA
    # =========================================================

    locality = (
        str(prop.get("locality", ""))
        .strip()
        .title()
    )

    city = (
        str(prop.get("city", ""))
        .strip()
        .title()
    )

    property_type = (
        str(
            prop.get(
                "property_type",
                "Apartment"
            )
        )
        .strip()
        .title()
    )

    bhk = prop.get(
        "bhk",
        2
    )

    area_sqft = float(
        prop.get(
            "area_sqft",
            1000
        )
    )

    # =========================================================
    # GEOCODING
    # =========================================================

    location_data = geocode_address(
        prop.get(
            "address",
            ""
        ),
        locality,
        city,
    )

    # =========================================================
    # LOCAL COMPARABLE PROPERTIES
    # =========================================================

    comparables = await get_comparables(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    print(
        "\n[PROPERTY VALUATION DEBUG]"
    )

    print(
        "locality:",
        locality
    )

    print(
        "city:",
        city
    )

    print(
        "property_type:",
        property_type
    )

    print(
        "bhk:",
        bhk
    )

    print(
        "area_sqft:",
        area_sqft
    )

    print(
        "comparables_count:",
        len(comparables)
    )

    print(
        "comparables:",
        comparables
    )

    # =========================================================
    # AVNESTER API
    # =========================================================

    api_val = await fetch_api_valuation(
        locality=locality,
        city=city,
        property_type=property_type,
        bhk=bhk,
        area_sqft=area_sqft,
    )

    print(
        "\n[AVNESTER VALUATION RESULT]"
    )

    print(
        "api_val:",
        api_val
    )

    # =========================================================
    # LOCAL COMPARABLE VALUATION
    # =========================================================

    risk_flags: list[str] = []

    comp_value = 0.0

    comparable_price_per_sqft = 0.0

    if comparables:

        comparable_ppsf = [
            c.get(
                "price_per_sqft_inr"
            )
            for c in comparables
            if c.get(
                "price_per_sqft_inr"
            )
            and c.get(
                "price_per_sqft_inr"
            ) > 0
        ]

        if comparable_ppsf:

            comparable_price_per_sqft = (
                sum(comparable_ppsf)
                / len(comparable_ppsf)
            )

            comp_value = (
                comparable_price_per_sqft
                * area_sqft
            )

        else:

            risk_flags.append(
                "Comparable properties do not "
                "have usable price-per-square-foot data."
            )

    else:

        risk_flags.append(
            "No comparable sales found "
            "in local PostgreSQL database."
        )

    # =========================================================
    # VALUATION DEBUG
    # =========================================================

    print(
        "\n[VALUATION CALCULATION DEBUG]"
    )

    print(
        "comparable_prices:",
        [
            c.get("price_inr")
            for c in comparables
        ]
    )

    print(
        "comparable_price_per_sqft:",
        comparable_price_per_sqft
    )

    print(
        "comp_value:",
        comp_value
    )

    # =========================================================
    # AVNESTER ESTIMATED VALUE
    # =========================================================

    api_est = api_val.get(
        "estimated_market_value_inr",
        0
    )

    try:
        api_est = float(
            api_est or 0
        )
    except (
        TypeError,
        ValueError
    ):
        api_est = 0.0

    # =========================================================
    # CHOOSE FINAL VALUATION
    # =========================================================

    if api_est > 0:

        # -----------------------------------------------------
        # AVnester has usable market data
        # -----------------------------------------------------

        estimated_value = api_est

        method = [
            "comparable_sales",
            "avnester",
        ]

        market_range_low = (
            api_val
            .get(
                "valuation_range_inr",
                {}
            )
            .get(
                "low",
                0
            )
        )

        market_range_high = (
            api_val
            .get(
                "valuation_range_inr",
                {}
            )
            .get(
                "high",
                0
            )
        )

        price_per_sqft = api_val.get(
            "price_per_sqft_inr",
            0
        )

    else:

        # -----------------------------------------------------
        # AVnester unavailable / unsupported
        # Use PostgreSQL comparables
        # -----------------------------------------------------

        estimated_value = comp_value

        method = [
            "comparable_sales",
            "postgresql",
        ]

        if comp_value > 0:

            market_range_low = (
                comp_value * 0.90
            )

            market_range_high = (
                comp_value * 1.10
            )

            price_per_sqft = (
                comparable_price_per_sqft
            )

            # -------------------------------------------------
            # Determine AVnester fallback reason
            # -------------------------------------------------

            supported = api_val.get(
                "supported",
                True
            )

            if supported is False:

                risk_flags.append(
                    "AVnester does not support "
                    "this location. Valuation uses "
                    "PostgreSQL comparable sales."
                )

            else:

                risk_flags.append(
                    "AVnester returned no matching "
                    "listings; PostgreSQL comparable "
                    "valuation used."
                )

        else:

            market_range_low = 0

            market_range_high = 0

            price_per_sqft = 0

            risk_flags.append(
                "No valuation data available from "
                "AVnester or PostgreSQL comparable database."
            )

    # =========================================================
    # COMPARE API AND LOCAL DATABASE
    # =========================================================

    if (
        comp_value > 0
        and api_est > 0
    ):

        difference = (
            abs(
                comp_value
                - api_est
            )
            / api_est
        )

    else:

        difference = 0.0

    # =========================================================
    # CONFIDENCE SCORE
    # =========================================================

    if (
        api_est > 0
        and comp_value > 0
    ):

        confidence_score = (
            0.90
            - (
                difference
                * 1.50
            )
        )

    elif api_est > 0:

        confidence_score = 0.70

    elif comp_value > 0:

        # More comparables = slightly higher confidence.
        comparable_count = len(
            comparables
        )

        confidence_score = min(
            0.80,
            0.50
            + (
                0.05
                * comparable_count
            ),
        )

    else:

        confidence_score = 0.0

    confidence_score = max(
        0.0,
        min(
            1.0,
            confidence_score
        ),
    )

    # =========================================================
    # ADDITIONAL RISK FLAGS
    # =========================================================

    if len(comparables) < 2:

        risk_flags.append(
            "Insufficient comparable "
            "properties available."
        )

    # =========================================================
    # EXPLANATION
    # =========================================================

    if api_est > 0:

        explanation = (
            f"Property valuation estimated at "
            f"₹{estimated_value:,.0f} using "
            f"AVnester market data and "
            f"{len(comparables)} local "
            f"comparable properties."
        )

    elif comp_value > 0:

        explanation = (
            "AVnester returned no matching "
            "live listings. Property valuation "
            f"estimated at ₹{estimated_value:,.0f} "
            f"using {len(comparables)} "
            "PostgreSQL comparable properties."
        )

    else:

        explanation = (
            "Property valuation could not be "
            "determined because no comparable "
            "or external market data was available."
        )

    # =========================================================
    # OPTIONAL GEMINI EXPLANATION
    # =========================================================

    if os.environ.get(
        "GEMINI_API_KEY"
    ):

        try:

            llm = ChatGoogleGenerativeAI(
                model="gemini-3.1-flash-lite"
            )

            prompt = f"""
You are a Property Valuation Assistant.

Explain the property valuation concisely.

Property:
{prop}

Final Estimated Value:
{estimated_value}

AVnester Estimated Value:
{api_est}

Local PostgreSQL Comparable Value:
{comp_value}

Average Comparable Price Per Sqft:
{comparable_price_per_sqft}

Comparables Found:
{len(comparables)}

Confidence:
{confidence_score:.2f}

Risk Flags:
{risk_flags}
"""

            response = llm.invoke(
                [
                    HumanMessage(
                        content=prompt
                    )
                ]
            )

            explanation = response.content

        except Exception:
            pass

    # =========================================================
    # FINAL OUTPUT
    # =========================================================

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
                    "source": (
                        "avnester"
                        if api_est > 0
                        else "postgresql"
                    ),
                },

                {
                    "agent": "property",
                    "field": "comparable_count",
                    "value": len(comparables),
                    "source": "postgresql",
                },

                {
                    "agent": "property",
                    "field": "average_comparable_price_per_sqft",
                    "value": comparable_price_per_sqft,
                    "source": "postgresql",
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
                "Square Yards",
                "PostgreSQL Comparable Database",
            ],
        },

        "errors":
            errors,
    }