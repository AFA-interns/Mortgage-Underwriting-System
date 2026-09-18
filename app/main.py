from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import uuid

from app.schemas import PropertyIntake, ValuationResponse, ValuationRange
from app.graph.graph import valuation_graph
from app.tools.external_api import fetch_api_valuation

app = FastAPI(title="Property Valuation Agent API - India")

@app.post("/api/v1/valuation/evaluate")
def evaluate_property(intake: PropertyIntake):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {"property": intake.model_dump()}
    
    # Run graph
    result = valuation_graph.invoke(initial_state, config=config)
    
    state = valuation_graph.get_state(config)
    
    # Check if interrupted for human review (next will contain the next node if paused)
    if "explanation" in state.next or (result.get("human_review_required") and state.next):
        return {
            "status": "PENDING_HUMAN_REVIEW",
            "thread_id": thread_id,
            "message": "Valuation requires human review due to low confidence or high risk.",
            "current_confidence": result.get("confidence"),
            "risk_flags": result.get("risk_flags")
        }
        
    # If it finished straight away
    return build_response(result)

class ResumeRequest(BaseModel):
    approved: bool
    notes: str = ""

@app.post("/api/v1/valuation/{thread_id}/resume")
def resume_valuation(thread_id: str, req: ResumeRequest):
    config = {"configurable": {"thread_id": thread_id}}
    state = valuation_graph.get_state(config)
    
    if not state.next:
        raise HTTPException(status_code=400, detail="Thread is not pending human review or does not exist.")
        
    if not req.approved:
        return {"status": "REJECTED", "message": "Valuation rejected by underwriter."}
        
    # Resume the graph (passing None continues from the interrupt)
    result = valuation_graph.invoke(None, config=config)
    
    return build_response(result)

def build_response(state_dict) -> dict:
    return {
        "estimated_market_value_inr": state_dict.get("final_value", {}).get("estimated_market_value_inr", 0),
        "valuation_range_inr": state_dict.get("final_value", {}).get("valuation_range_inr", {"low": 0, "high": 0}),
        "price_per_sqft_inr": state_dict.get("api_valuation", {}).get("price_per_sqft_inr", 0),
        "measurement_basis": state_dict.get("api_valuation", {}).get("measurement_basis", "carpet_area"),
        "comparable_count": len(state_dict.get("candidate_comps", [])),
        "comparables": state_dict.get("candidate_comps", []),
        "confidence_score": state_dict.get("confidence", {}).get("score", 0),
        "confidence_label": state_dict.get("confidence", {}).get("label", "UNKNOWN"),
        "risk_flags": state_dict.get("risk_flags", []),
        "human_review_required": state_dict.get("human_review_required", False),
        "method": ["comparable_sales", "mock_external_api"],
        "sources": ["Nominatim Geocoder", "Mock Zapkey AVM", "Local Dummy DB"],
        "explanation": state_dict.get("explanation", "")
    }

@app.get("/api/mock-external/valuation")
def mock_external_avm(locality: str, city: str, property_type: str, bhk: int, area_sqft: float):
    return fetch_api_valuation(locality, city, property_type, bhk, area_sqft)
