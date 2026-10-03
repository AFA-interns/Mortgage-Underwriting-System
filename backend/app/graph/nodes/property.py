import os

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.tools.geocoder import geocode_address
from app.tools.property_database import get_database_comparables
from app.tools.external_api import fetch_api_valuation

from app.graph.property_state import AgentState


# ============================================================
# 1. INTAKE NODE
# ============================================================

def intake_node(state: AgentState) -> AgentState:

    prop = state.get("property", {})

    prop["locality"] = prop.get("locality", "").title()
    prop["city"] = prop.get("city", "").title()
    prop["property_type"] = prop.get(
        "property_type",
        ""
    ).title()

    return {
        "property": prop
    }


# ============================================================
# 2. LOCATION NODE
# ============================================================

def location_node(state: AgentState) -> AgentState:

    prop = state.get("property", {})

    loc_data = geocode_address(
        prop.get("address", ""),
        prop.get("locality", ""),
        prop.get("city", ""),
    )

    return {
        "location": loc_data
    }


# ============================================================
# 3. COMPARABLE PROPERTY NODE
# ============================================================

async def comps_node(state: AgentState) -> AgentState:

    prop = state.get("property", {})

    comps = await get_database_comparables(
        city=prop.get("city", ""),
        locality=prop.get("locality", ""),
        bedrooms=prop.get("bhk", 1),
    )

    return {
        "candidate_comps": comps
    }


# ============================================================
# 4. EXTERNAL API VALUATION NODE
# ============================================================

async def api_valuation_node(state: AgentState) -> AgentState:

    prop = state.get("property", {})

    api_val = await fetch_api_valuation(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000),
    )

    return {
        "api_valuation": api_val
    }


# ============================================================
# 5. RECONCILIATION NODE
# ============================================================

def reconcile_node(state: AgentState) -> AgentState:

    comps = state.get("candidate_comps", [])
    api_val = state.get("api_valuation", {})
    prop = state.get("property", {})

    risk_flags = []

    # ---------------------------------------------------------
    # 1. Calculate valuation from PostgreSQL comparables
    # ---------------------------------------------------------

    comp_value = 0.0
    average_price_per_sqft = 0.0

    if comps:

        target_area = prop.get("area_sqft", 0)

        try:
            target_area = float(target_area or 0)
        except (TypeError, ValueError):
            target_area = 0.0

        prices_per_sqft = [
            c.get("price_per_sqft")
            for c in comps
            if c.get("price_per_sqft") is not None
            and c.get("price_per_sqft") > 0
        ]

        if prices_per_sqft and target_area > 0:

            average_price_per_sqft = (
                sum(prices_per_sqft)
                / len(prices_per_sqft)
            )

            comp_value = (
                average_price_per_sqft
                * target_area
            )

        else:

            risk_flags.append(
                "Comparable properties do not have usable "
                "price-per-square-foot data."
            )

    else:

        risk_flags.append(
            "No comparable sales found in PostgreSQL "
            "property database."
        )

    # ---------------------------------------------------------
    # 2. Check AVnester valuation
    # ---------------------------------------------------------

    api_est = api_val.get(
        "estimated_market_value_inr",
        0
    )

    try:
        api_est = float(api_est or 0)
    except (TypeError, ValueError):
        api_est = 0.0

    api_supported = api_val.get(
        "supported",
        True
    )

    # ---------------------------------------------------------
    # 3. Choose valuation method
    # ---------------------------------------------------------

    if api_est > 0:

        # AVnester has usable valuation data
        final_estimate = api_est

        if comp_value > 0:

            difference = (
                abs(comp_value - api_est)
                / api_est
            )

        else:

            difference = 0.0

        valuation_range = api_val.get(
            "valuation_range_inr",
            {
                "low": api_est * 0.90,
                "high": api_est * 1.10,
            },
        )

        method = "AVnester + comparable sales"

        # If AVnester supplied a price/sqft, use it.
        # Otherwise use the PostgreSQL comparable value.
        api_price_per_sqft = api_val.get(
            "price_per_sqft_inr",
            0
        )

        try:
            api_price_per_sqft = float(
                api_price_per_sqft or 0
            )
        except (TypeError, ValueError):
            api_price_per_sqft = 0.0

        if api_price_per_sqft > 0:

            final_price_per_sqft = (
                api_price_per_sqft
            )

        else:

            final_price_per_sqft = (
                average_price_per_sqft
            )

    elif comp_value > 0:

        # -----------------------------------------------------
        # AVnester unavailable → PostgreSQL fallback
        # -----------------------------------------------------

        final_estimate = comp_value

        difference = 0.0

        valuation_range = {
            "low": comp_value * 0.90,
            "high": comp_value * 1.10,
        }

        method = "PostgreSQL comparable sales"

        # PostgreSQL is the source of the price/sqft
        final_price_per_sqft = (
            average_price_per_sqft
        )

        if not api_supported:

            risk_flags.append(
                "AVnester does not support this location. "
                "Valuation uses PostgreSQL comparable sales."
            )

        else:

            risk_flags.append(
                "AVnester returned no usable valuation data. "
                "Valuation uses PostgreSQL comparable sales."
            )

    else:

        # -----------------------------------------------------
        # No valuation source available
        # -----------------------------------------------------

        final_estimate = 0.0

        difference = 1.0

        valuation_range = {
            "low": 0,
            "high": 0,
        }

        method = "No usable valuation source"

        final_price_per_sqft = 0.0

        risk_flags.append(
            "No usable valuation data available."
        )

    # ---------------------------------------------------------
    # 4. Calculate confidence
    # ---------------------------------------------------------

    if final_estimate > 0 and comp_value > 0:

        if api_est > 0:

            confidence_score = (
                0.90
                - (difference * 1.50)
            )

        else:

            # Comparable-only valuation
            confidence_score = 0.70

    elif final_estimate > 0:

        confidence_score = 0.70

    else:

        confidence_score = 0.20

    confidence_score = max(
        0.0,
        min(1.0, confidence_score)
    )

    # ---------------------------------------------------------
    # 5. Determine confidence label
    # ---------------------------------------------------------

    if confidence_score >= 0.80:

        conf_label = "HIGH"

    elif confidence_score >= 0.60:

        conf_label = "MEDIUM"

    else:

        conf_label = "LOW"

    # ---------------------------------------------------------
    # 6. Human review
    # ---------------------------------------------------------

    human_review = (
        confidence_score < 0.60
        or len(comps) < 2
    )

    if human_review:

        risk_flags.append(
            "Insufficient comparable data or low confidence."
        )

    # ---------------------------------------------------------
    # 7. Debug information
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("PROPERTY VALUATION RECONCILIATION")
    print("=" * 70)

    print(
        f"Comparables found        : {len(comps)}"
    )

    print(
        f"Average price/sqft       : "
        f"₹{average_price_per_sqft:,.2f}"
    )

    print(
        f"PostgreSQL comp value    : "
        f"₹{comp_value:,.2f}"
    )

    print(
        f"AVnester value           : "
        f"₹{api_est:,.2f}"
    )

    print(
        f"Final estimated value    : "
        f"₹{final_estimate:,.2f}"
    )

    print(
        f"Final price/sqft         : "
        f"₹{final_price_per_sqft:,.2f}"
    )

    print(
        f"Confidence               : "
        f"{confidence_score:.2f} ({conf_label})"
    )

    print(
        f"Method                   : "
        f"{method}"
    )

    print(
        f"Human review             : "
        f"{human_review}"
    )

    print("=" * 70)

    # ---------------------------------------------------------
    # 8. Return reconciliation result
    # ---------------------------------------------------------

    return {

        "confidence": {
            "score": round(
                confidence_score,
                2
            ),
            "label": conf_label,
        },

        "risk_flags": risk_flags,

        "human_review_required": human_review,

        "final_value": {

            "estimated_market_value_inr": round(
                final_estimate,
                2
            ),

            "valuation_range_inr": {

                "low": round(
                    valuation_range.get(
                        "low",
                        0
                    ),
                    2
                ),

                "high": round(
                    valuation_range.get(
                        "high",
                        0
                    ),
                    2
                ),
            },

            # IMPORTANT:
            # This was missing before.
            "price_per_sqft_inr": round(
                final_price_per_sqft,
                2
            ),

            "method": method,
        },
    }


# ============================================================
# 6. EXPLANATION NODE
# ============================================================

def explanation_node(state: AgentState) -> AgentState:

    if not os.environ.get("GEMINI_API_KEY"):

        return {
            "explanation": (
                "Property valued at ₹{:,.0f} using {}. "
                "The valuation used {} comparable properties "
                "with an average comparable rate of ₹{:,.2f} "
                "per sq ft."
            ).format(

                state.get(
                    "final_value",
                    {}
                ).get(
                    "estimated_market_value_inr",
                    0
                ),

                state.get(
                    "final_value",
                    {}
                ).get(
                    "method",
                    "available market data"
                ),

                len(
                    state.get(
                        "candidate_comps",
                        []
                    )
                ),

                state.get(
                    "final_value",
                    {}
                ).get(
                    "price_per_sqft_inr",
                    0
                ),
            )
        }

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite"
    )

    prompt = f"""
You are a Property Valuation Assistant.

Explain the property valuation concisely and factually.

Property:
{state.get('property', {})}

AVnester Estimated Value:
{state.get('api_valuation', {}).get('estimated_market_value_inr', 0)}

PostgreSQL Comparable Value:
{state.get('final_value', {}).get('estimated_market_value_inr', 0)}

Average Comparable Price Per Sqft:
{state.get('final_value', {}).get('price_per_sqft_inr', 0)}

Comparables Found:
{len(state.get('candidate_comps', []))}

Confidence:
{state.get('confidence', {}).get('label')}
({state.get('confidence', {}).get('score')})

Risk Flags:
{state.get('risk_flags', [])}

Valuation Method:
{state.get('final_value', {}).get('method')}
"""

    try:

        response = llm.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        explanation = response.content

    except Exception as e:

        explanation = (
            f"Error generating explanation: {str(e)}"
        )

    return {
        "explanation": explanation
    }