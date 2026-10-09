"""FastAPI application — exposes underwriting API endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.avnester import search_properties

from app.graph.state import UnderwritingState
from app.graph.workflow import build_underwriting_graph, build_underwriting_graph_with_checkpointer
from app.models.decision import DecisionResult
from app.services.audit import audit_store, create_audit_record
from app.document_ingestion.agent import DocumentIngestionAgent
from app.models.document_ingestion_state import DocumentIngestionOutput

from app.models.property_valuation import (
    PropertyIntake,
    ValuationResponse,
    ValuationRange,
)

from app.graph.property_workflow import valuation_graph
from app.tools.external_api import fetch_api_valuation


app = FastAPI(
    title="Mortgage Underwriting API",
    description=(
        "Agentic AI Mortgage Underwriting System — "
        "Document Ingestion + Decision Agent"
    ),
    version="0.1.0",
)


# =======================================================
# CORS
# =======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =======================================================
# APPLICATION CACHE
# =======================================================

PROCESSED_APPLICATIONS: Dict[
    str,
    DocumentIngestionOutput
] = {}


# =======================================================
# UNDERWRITING REQUEST
# =======================================================

class UnderwritingRequest(BaseModel):

    application_id: str

    raw_document_paths: list[str] = []

    borrower_profile: dict[str, Any] = {}

    document_analysis: dict[str, Any] = {}

    credit_analysis: dict[str, Any] = {}

    property_analysis: dict[str, Any] = {}

    compliance_analysis: dict[str, Any] = {}


# =======================================================
# HEALTH CHECK
# =======================================================

@app.get("/health")
async def health() -> dict[str, str]:

    return {
        "status": "ok"
    }


# =======================================================
# PROPERTY VALUATION AGENT
# =======================================================

@app.post("/api/v1/valuation/evaluate")
async def evaluate_property(
    intake: PropertyIntake,
):

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_state = {
        "property": intake.model_dump()
    }

    # ---------------------------------------------------
    # Run valuation graph asynchronously
    # ---------------------------------------------------

    result = await valuation_graph.ainvoke(
        initial_state,
        config=config,
    )

    state = valuation_graph.get_state(
        config
    )

    # ---------------------------------------------------
    # Human review check
    # ---------------------------------------------------

    if (
        "explanation" in state.next
        or (
            result.get(
                "human_review_required"
            )
            and state.next
        )
    ):

        return {

            "status": "PENDING_HUMAN_REVIEW",

            "thread_id": thread_id,

            "message": (
                "Valuation requires human review "
                "due to low confidence or high risk."
            ),

            "current_confidence": result.get(
                "confidence"
            ),

            "risk_flags": result.get(
                "risk_flags"
            ),
        }

    return _build_valuation_response(
        result
    )


# =======================================================
# HUMAN REVIEW
# =======================================================

class ResumeRequest(BaseModel):

    approved: bool

    notes: str = ""


@app.post(
    "/api/v1/valuation/{thread_id}/resume"
)
async def resume_valuation(
    thread_id: str,
    req: ResumeRequest,
):

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    state = valuation_graph.get_state(
        config
    )

    if not state.next:

        raise HTTPException(
            status_code=400,
            detail=(
                "Thread is not pending human "
                "review or does not exist."
            ),
        )

    # ---------------------------------------------------
    # Rejected by human reviewer
    # ---------------------------------------------------

    if not req.approved:

        return {

            "status": "REJECTED",

            "message": (
                "Valuation rejected by underwriter."
            ),
        }

    # ---------------------------------------------------
    # Resume graph asynchronously
    # ---------------------------------------------------

    result = await valuation_graph.ainvoke(
        None,
        config=config,
    )

    return _build_valuation_response(
        result
    )


# =======================================================
# BUILD FINAL VALUATION RESPONSE
# =======================================================

def _build_valuation_response(
    state_dict,
) -> dict:

    final_value = state_dict.get(
        "final_value",
        {}
    )

    api_valuation = state_dict.get(
        "api_valuation",
        {}
    )

    candidate_comps = state_dict.get(
        "candidate_comps",
        []
    )

    confidence = state_dict.get(
        "confidence",
        {}
    )

    # ---------------------------------------------------
    # IMPORTANT:
    #
    # price_per_sqft_inr is calculated by reconcile_node()
    # and stored inside final_value.
    #
    # Previously this code incorrectly looked only inside
    # api_valuation, which caused 0 for Bangalore because
    # AVnester does not support Bangalore.
    # ---------------------------------------------------

    price_per_sqft = final_value.get(
        "price_per_sqft_inr",
        0
    )

    # Safety fallback:
    # If final_value does not contain it, try AVnester.
    if not price_per_sqft:

        price_per_sqft = api_valuation.get(
            "price_per_sqft_inr",
            0
        )

    # ---------------------------------------------------
    # Return final response
    # ---------------------------------------------------

    return {

        "estimated_market_value_inr":
            final_value.get(
                "estimated_market_value_inr",
                0,
            ),

        "valuation_range_inr":
            final_value.get(
                "valuation_range_inr",
                {
                    "low": 0,
                    "high": 0,
                },
            ),

        "price_per_sqft_inr":
            price_per_sqft,

        "measurement_basis":
            api_valuation.get(
                "measurement_basis",
                "carpet_area",
            ),

        "comparable_count":
            len(candidate_comps),

        "comparables":
            candidate_comps,

        "confidence_score":
            confidence.get(
                "score",
                0,
            ),

        "confidence_label":
            confidence.get(
                "label",
                "UNKNOWN",
            ),

        "risk_flags":
            state_dict.get(
                "risk_flags",
                [],
            ),

        "human_review_required":
            state_dict.get(
                "human_review_required",
                False,
            ),

        "method":
            final_value.get(
                "method",
                "unknown"
            ),

        "sources": [
            "Nominatim Geocoder",
            "AVnester",
            "Square Yards",
            "PostgreSQL Property Database",
        ],

        "explanation":
            state_dict.get(
                "explanation",
                "",
            ),
    }


# =======================================================
# MAIN UNDERWRITING WORKFLOW WITH HUMAN REVIEW
# =======================================================

class UnderwritingResumeRequest(BaseModel):
    approved: bool
    notes: str = ""


@app.post("/api/v1/underwriting/evaluate")
async def evaluate_underwriting(
    request: UnderwritingRequest,
):
    """
    Run the full underwriting workflow with human review support.
    
    The workflow runs through:
    1. Document Ingestion
    2. Credit Analysis
    3. Property Valuation
    4. Compliance Check
    5. Decision Making
    
    If the workflow pauses for human review (SUSPEND decision),
    the client can resume via /api/v1/underwriting/{thread_id}/resume
    """
    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_state = {
        "application_id": request.application_id,
        "borrower_id": f"BORR-{request.application_id}",
        "raw_document_paths": request.raw_document_paths,
        "borrower_profile": request.borrower_profile,
        "document_analysis": request.document_analysis,
        "credit_analysis": request.credit_analysis,
        "property_analysis": request.property_analysis,
        "compliance_analysis": request.compliance_analysis,
        "errors": [],
    }

# Use pre-compiled graph with checkpointer for human review support
    app_graph = build_underwriting_graph_with_checkpointer()

    # Run the workflow
    result = await app_graph.ainvoke(initial_state, config=config)

    # Check if human review is required
    state = app_graph.get_state(config)

    # Check if suspended for human review
    if state.next and "human_review" in state.next:
        decision = result.get("decision", {})
        return {
            "status": "PENDING_HUMAN_REVIEW",
            "thread_id": thread_id,
            "message": (
                "Underwriting decision suspended for human review. "
                f"Preliminary decision: {decision.get('decision', 'UNKNOWN')}"
            ),
            "preliminary_decision": decision.get("decision"),
            "risk_score": decision.get("risk_score"),
            "confidence": decision.get("confidence"),
            "flags": decision.get("flags", []),
            "contradictions": result.get("contradictions", []),
        }

    # Decision completed without human review
    decision = result.get("decision", {})
    return {
        "status": "COMPLETED",
        "thread_id": thread_id,
        "application_id": request.application_id,
        "decision": decision.get("decision"),
        "risk_score": decision.get("risk_score"),
        "confidence": decision.get("confidence"),
        "risk_level": decision.get("risk_level"),
        "rationale": decision.get("rationale"),
        "flags": decision.get("flags", []),
        "contradictions": result.get("contradictions", []),
        "underwriting_report": result.get("underwriting_report", ""),
    }


@app.post("/api/v1/underwriting/{thread_id}/resume")
async def resume_underwriting(
    thread_id: str,
    req: UnderwritingResumeRequest,
):
    """
    Resume an underwriting workflow that was paused for human review.
    
    The underwriter provides their approval/rejection decision
    and the workflow continues to final decision.
    """
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

# Use pre-compiled graph with checkpointer for human review support
    app_graph = build_underwriting_graph_with_checkpointer()

    state = app_graph.get_state(config)

    if not state.next or "human_review" not in state.next:
        raise HTTPException(
            status_code=400,
            detail=(
                "Thread is not pending human "
                "review or does not exist."
            ),
        )

    # If rejected by human reviewer
    if not req.approved:
        return {
            "status": "REJECTED_BY_UNDERWRITER",
            "message": "Underwriting rejected by underwriter.",
            "notes": req.notes,
        }

    # Resume the graph with human approval
    # The human review node will incorporate the approval
    result = await app_graph.ainvoke(None, config=config)

    decision = result.get("decision", {})
    return {
        "status": "COMPLETED",
        "thread_id": thread_id,
        "application_id": result.get("application_id"),
        "decision": decision.get("decision"),
        "risk_score": decision.get("risk_score"),
        "confidence": decision.get("confidence"),
        "risk_level": decision.get("risk_level"),
        "rationale": decision.get("rationale"),
        "flags": decision.get("flags", []),
        "contradictions": result.get("contradictions", []),
        "underwriting_report": result.get("underwriting_report", ""),
    }


# =======================================================
# AVNESTER / EXTERNAL VALUATION TEST ENDPOINT
# =======================================================

@app.get(
    "/api/mock-external/valuation"
)
async def mock_external_avm(
    locality: str,
    city: str,
    property_type: str,
    bhk: int,
    area_sqft: float,
):

    return await fetch_api_valuation(
        locality,
        city,
        property_type,
        bhk,
        area_sqft,
    )