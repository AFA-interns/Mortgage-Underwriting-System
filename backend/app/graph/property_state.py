from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    property: dict
    location: dict
    candidate_comps: List[dict]
    api_valuation: dict
    final_value: dict
    confidence: dict
    risk_flags: List[str]
    human_review_required: bool
    explanation: str
