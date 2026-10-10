from app.services.llm import explain
from app.tools.geocoder import geocode_address
from app.tools.external_api import fetch_api_valuation
from app.tools.local_comparables import fetch_local_valuation
from app.tools.comparables_db import get_comparables_sync
from app.graph.property_state import AgentState


def intake_node(state: AgentState) -> AgentState:
    prop = state.get("property", {})
    prop["locality"] = prop.get("locality", "").title()
    prop["city"] = prop.get("city", "").title()
    prop["property_type"] = prop.get("property_type", "").title()
    return {"property": prop}


def location_node(state: AgentState) -> AgentState:
    prop = state.get("property", {})
    loc_data = geocode_address(prop.get("address", ""), prop.get("locality", ""), prop.get("city", ""))
    return {"location": loc_data}


def comps_node(state: AgentState) -> AgentState:
    """Comparable listings from the scraped PostgreSQL property database
    (SquareYards/Housing/MagicBricks/..., see property_data/ and
    app.tools.comparables_db) - quality-scored and deduplicated.

    get_comparables() is async (it opens its own async DB session);
    get_comparables_sync() bridges it so this node stays a plain sync
    LangGraph node like the rest of the graph, whether or not the calling
    endpoint happens to be running on an active event loop.
    """
    prop = state.get("property", {})
    comps = get_comparables_sync(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000),
    )
    return {"candidate_comps": comps}


def api_valuation_node(state: AgentState) -> AgentState:
    prop = state.get("property", {})
    api_val = fetch_api_valuation(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000),
    )
    return {"api_valuation": api_val}


def reconcile_node(state: AgentState) -> AgentState:
    """Combine three independent valuation sources, in order of trust:

    1. AVnester live listings (api_valuation_node) - primary when it has
       a usable estimate. The scraped database comparables (2) are then
       used as a cross-check: material disagreement lowers confidence
       rather than being silently discarded.
    2. The scraped PostgreSQL comparables database (comps_node) - used
       outright when AVnester has nothing usable for this location.
    3. The simpler locality/city median fallback (local_comparables) -
       only reached when both of the above come up empty.
    """
    comps = state.get("candidate_comps", [])
    api_val = state.get("api_valuation", {})
    prop = state.get("property", {})

    risk_flags: list[str] = []

    # ---- Price/sqft from the database comparables (cross-check / fallback) ----
    comp_value = 0.0
    average_price_per_sqft = 0.0
    if comps:
        target_area = float(prop.get("area_sqft") or 0)
        prices_per_sqft = [c.get("price_per_sqft_inr") for c in comps if c.get("price_per_sqft_inr")]
        if prices_per_sqft and target_area > 0:
            average_price_per_sqft = sum(prices_per_sqft) / len(prices_per_sqft)
            comp_value = average_price_per_sqft * target_area
        else:
            risk_flags.append("Database comparables do not have usable price-per-square-foot data.")
    else:
        risk_flags.append("No comparable sales found in the scraped property database.")

    # ---- AVnester ----
    api_est = float(api_val.get("estimated_market_value_inr") or 0)
    if not api_val.get("supported", True) and api_val.get("scope_message"):
        risk_flags.append(api_val["scope_message"])

    # ---- Choose the valuation ----
    if api_est > 0:
        value_source = "avnester"
        final_estimate = api_est
        valuation_range = api_val.get(
            "valuation_range_inr", {"low": api_est * 0.90, "high": api_est * 1.10}
        )
        final_price_per_sqft = api_val.get("price_per_sqft_inr") or average_price_per_sqft
        if comp_value > 0:
            difference = abs(comp_value - api_est) / api_est
            if difference > 0.25:
                risk_flags.append(
                    "Scraped database comparables disagree with AVnester by more "
                    "than 25%; valuation confidence lowered accordingly."
                )
        else:
            difference = 0.0
    elif comp_value > 0:
        value_source = "scraped_db"
        final_estimate = comp_value
        difference = 0.0
        valuation_range = {"low": comp_value * 0.90, "high": comp_value * 1.10}
        final_price_per_sqft = average_price_per_sqft
        if not api_val.get("supported", True):
            risk_flags.append(
                "AVnester does not support this location; valuation uses the "
                "scraped property comparables database instead."
            )
        else:
            risk_flags.append(
                "AVnester returned no usable listings; valuation uses the "
                "scraped property comparables database instead."
            )
    else:
        local_val = fetch_local_valuation(
            locality=prop.get("locality", ""),
            city=prop.get("city", ""),
            bhk=prop.get("bhk"),
            area_sqft=prop.get("area_sqft", 0),
        )
        local_est = local_val.get("estimated_market_value_inr", 0)
        if local_est > 0:
            value_source = "local_db"
            comps = local_val["comparables"]
            final_estimate = local_est
            difference = 0.0
            valuation_range = local_val["valuation_range_inr"]
            final_price_per_sqft = local_val.get("price_per_sqft_inr", 0)
            risk_flags.append(
                "AVnester and the scraped comparables database both had no usable "
                "listings; valuation uses the local median fallback instead."
            )
        else:
            value_source = "none"
            final_estimate = 0.0
            difference = 1.0
            valuation_range = {"low": 0, "high": 0}
            final_price_per_sqft = 0.0
            risk_flags.append("No comparable AVnester, database, or local listings found.")

    # ---- Confidence ----
    if final_estimate > 0 and comp_value > 0 and api_est > 0:
        confidence_score = max(0.0, min(1.0, 0.90 - difference * 1.50))
    elif final_estimate > 0:
        confidence_score = 0.70
    else:
        confidence_score = 0.0

    conf_label = "HIGH" if confidence_score >= 0.80 else "MEDIUM" if confidence_score >= 0.60 else "LOW"

    human_review = confidence_score < 0.60 or len(comps) < 2
    if human_review:
        risk_flags.append("Low confidence or insufficient comparable listings.")

    return {
        "confidence": {"score": round(confidence_score, 2), "label": conf_label},
        "risk_flags": risk_flags,
        "human_review_required": human_review,
        "value_source": value_source,
        "candidate_comps": comps,
        "api_valuation": api_val,
        "final_value": {
            "estimated_market_value_inr": round(final_estimate, 2),
            "valuation_range_inr": {
                "low": round(valuation_range.get("low", 0), 2),
                "high": round(valuation_range.get("high", 0), 2),
            },
            "price_per_sqft_inr": round(final_price_per_sqft, 2),
        },
    }


def explanation_node(state: AgentState) -> AgentState:
    value = state.get("final_value", {}).get("estimated_market_value_inr")
    comps = state.get("candidate_comps", [])
    conf = state.get("confidence", {})
    fallback = "Property valued at {} based on {} comparable listings.".format(value, len(comps))
    explanation = explain(
        system=(
            "You are a property valuation assistant. Explain the valuation in 2-3 plain "
            "sentences using only the figures given. Never give or imply a loan verdict."
        ),
        prompt="\n".join(
            [
                f"Property: {state.get('property')}",
                f"Estimated value: {value}",
                f"Comparable listings: {len(comps)}",
                f"Confidence: {conf.get('label')} ({conf.get('score')})",
                f"Risk flags: {state.get('risk_flags')}",
            ]
        ),
        fallback=fallback,
    )
    return {"explanation": explanation}
