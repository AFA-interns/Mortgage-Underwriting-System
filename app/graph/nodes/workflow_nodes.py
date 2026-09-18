import os
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.tools.geocoder import geocode_address
from app.tools.comparables_db import get_comparables
from app.tools.external_api import fetch_api_valuation
from app.graph.state import AgentState

def intake_node(state: AgentState) -> AgentState:
    # Normalize inputs
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
    prop = state.get("property", {})
    comps = get_comparables(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000)
    )
    return {"candidate_comps": comps}

def api_valuation_node(state: AgentState) -> AgentState:
    prop = state.get("property", {})
    api_val = fetch_api_valuation(
        locality=prop.get("locality", ""),
        city=prop.get("city", ""),
        property_type=prop.get("property_type", ""),
        bhk=prop.get("bhk", 1),
        area_sqft=prop.get("area_sqft", 1000)
    )
    return {"api_valuation": api_val}

def reconcile_node(state: AgentState) -> AgentState:
    comps = state.get("candidate_comps", [])
    api_val = state.get("api_valuation", {})
    
    risk_flags = []
    
    # Comps calculation
    comp_value = 0
    if comps:
        comp_value = sum(c['price_inr'] for c in comps) / len(comps)
    else:
        risk_flags.append("No comparable sales found in local database.")
        
    api_est = api_val.get("estimated_market_value_inr", 0)
    
    # Compare
    difference = 0
    if comp_value > 0 and api_est > 0:
        difference = abs(comp_value - api_est) / api_est
    elif comp_value == 0:
        difference = 1.0 # High difference if we lack one side
    
    confidence_score = 0.9 - (difference * 1.5)
    if confidence_score < 0: confidence_score = 0
    
    human_review = False
    conf_label = "HIGH"
    
    if confidence_score < 0.6 or len(comps) < 2:
        human_review = True
        conf_label = "LOW"
        risk_flags.append("High variance between Comps and Market API, or insufficient data.")
    elif confidence_score < 0.8:
        conf_label = "MEDIUM"
        
    return {
        "confidence": {"score": round(confidence_score, 2), "label": conf_label},
        "risk_flags": risk_flags,
        "human_review_required": human_review,
        "final_value": {
            "estimated_market_value_inr": api_est, # Defaulting to API if comps are weak
            "valuation_range_inr": api_val.get("valuation_range_inr", {})
        }
    }

def explanation_node(state: AgentState) -> AgentState:
    # If API key is missing, mock the explanation
    if not os.environ.get("GEMINI_API_KEY"):
        return {"explanation": "Mock Explanation: Property valued at {} based on API and {} comparables.".format(
            state.get("final_value", {}).get("estimated_market_value_inr"),
            len(state.get("candidate_comps", []))
        )}
        
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    
    prompt = f"""
    You are a Property Valuation Assistant. Explain the valuation concisely.
    Property: {state['property']}
    API Estimated Value: {state['api_valuation'].get('estimated_market_value_inr')}
    Comparables Found: {len(state['candidate_comps'])}
    Confidence: {state['confidence']['label']} ({state['confidence']['score']})
    Risk Flags: {state['risk_flags']}
    """
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        explanation = response.content
    except Exception as e:
        explanation = f"Error generating explanation: {str(e)}"
        
    return {"explanation": explanation}
