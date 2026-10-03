from app.services.llm import explain
from app.tools.geocoder import geocode_address
from app.tools.external_api import fetch_api_valuation
from app.tools.local_comparables import fetch_local_valuation
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


def api_valuation_node(state: AgentState) -> AgentState:
    prop = state.get("property", {})
    api_val = fetch_api_valuation(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000)
    )
    return {"api_valuation": api_val, "candidate_comps": api_val.get("comparables", [])}


def reconcile_node(state: AgentState) -> AgentState:
    comps = state.get("candidate_comps", [])
    api_val = state.get("api_valuation", {})
    prop = state.get("property", {})

    risk_flags = []
    value_source = "avnester"

    if not api_val.get("supported", True) and api_val.get("scope_message"):
        risk_flags.append(api_val["scope_message"])

    api_est = api_val.get("estimated_market_value_inr", 0)

    if api_est <= 0:
        # AVnester has nothing usable - fall back to the locally stored
        # comparables database (scraped listings; see app.tools.local_comparables).
        local_val = fetch_local_valuation(
            locality=prop.get("locality", ""), city=prop.get("city", ""),
            bhk=prop.get("bhk"), area_sqft=prop.get("area_sqft", 0),
        )
        if local_val.get("estimated_market_value_inr", 0) > 0:
            value_source = "local_db"
            api_val = {**local_val, "api_confidence_score": 0.65 if local_val.get("scope") == "locality" else 0.55}
            comps = local_val["comparables"]
            api_est = local_val["estimated_market_value_inr"]
            risk_flags.append(
                "AVnester returned no usable listings; valuation uses the "
                "local comparables database instead."
            )
        else:
            risk_flags.append("No comparable AVnester or local-database listings found.")

    confidence_score = api_val.get("api_confidence_score", 0) if api_est > 0 else 0

    human_review = False
    conf_label = "HIGH"

    if confidence_score < 0.6 or len(comps) < 2:
        human_review = True
        conf_label = "LOW"
        risk_flags.append("Low confidence or insufficient comparable listings.")
    elif confidence_score < 0.8:
        conf_label = "MEDIUM"

    return {
        "confidence": {"score": round(confidence_score, 2), "label": conf_label},
        "risk_flags": risk_flags,
        "human_review_required": human_review,
        "value_source": value_source,
        "candidate_comps": comps,
        "api_valuation": api_val,  # may now be the local-DB result, not AVnester's
        "final_value": {
            "estimated_market_value_inr": api_est,
            "valuation_range_inr": api_val.get("valuation_range_inr", {}),
        }
    }


def explanation_node(state: AgentState) -> AgentState:
    value = state.get("final_value", {}).get("estimated_market_value_inr")
    comps = state.get("candidate_comps", [])
    conf = state.get("confidence", {})
    fallback = "Property valued at {} based on {} AVnester comparables.".format(value, len(comps))
    explanation = explain(
        system=(
            "You are a property valuation assistant. Explain the valuation in 2-3 plain "
            "sentences using only the figures given. Never give or imply a loan verdict."
        ),
        prompt="\n".join([
            f"Property: {state.get('property')}",
            f"Estimated value: {value}",
            f"Comparable listings: {len(comps)}",
            f"Confidence: {conf.get('label')} ({conf.get('score')})",
            f"Risk flags: {state.get('risk_flags')}",
        ]),
        fallback=fallback,
    )
    return {"explanation": explanation}
