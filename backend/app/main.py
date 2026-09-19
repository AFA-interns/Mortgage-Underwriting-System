"""FastAPI application — exposes underwriting API endpoints."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, List, Optional, Dict

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph.state import UnderwritingState
from app.graph.workflow import build_underwriting_graph
from app.models.decision import DecisionResult
from app.services.audit import audit_store, create_audit_record
from app.document_ingestion.agent import DocumentIngestionAgent
from app.models.document_ingestion_state import DocumentIngestionOutput

app = FastAPI(
    title="Mortgage Underwriting API",
    description="Agentic AI Mortgage Underwriting System — Document Ingestion + Decision Agent",
    version="0.1.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session cache for processed document ingestion packages
PROCESSED_APPLICATIONS: Dict[str, DocumentIngestionOutput] = {}


class UnderwritingRequest(BaseModel):
    application_id: str
    borrower_profile: dict[str, Any] = {}
    document_analysis: dict[str, Any] = {}
    credit_analysis: dict[str, Any] = {}
    property_analysis: dict[str, Any] = {}
    compliance_analysis: dict[str, Any] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/underwriting/{application_id}/run")
async def run_underwriting(application_id: str, request: UnderwritingRequest) -> dict[str, Any]:
    """Run the full Decision Agent pipeline."""
    state: UnderwritingState = {
        "application_id": application_id,
        "borrower_profile": request.borrower_profile,
        "document_analysis": request.document_analysis,
        "credit_analysis": request.credit_analysis,
        "property_analysis": request.property_analysis,
        "compliance_analysis": request.compliance_analysis,
        "errors": [],
    }

    try:
        graph = build_underwriting_graph()
        compiled = graph.compile()
        result = compiled.invoke(state)

        # Audit — decision is a dict from GraphState; wrap in DecisionResult if valid
        decision_dict = result.get("decision") or {}
        final_decision = None
        try:
            final_decision = DecisionResult.model_validate(decision_dict)
        except Exception:
            final_decision = None
        create_audit_record(
            application_id=application_id,
            final_decision=final_decision,
            errors=[e.get("message", "") for e in result.get("errors", [])],
        )

        return {
            "application_id": application_id,
            "decision": result.get("decision"),
            "report": result.get("underwriting_report"),
            "human_review_required": result.get("human_review_required", True),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Decision pipeline failed: {e}",
        ) from e


@app.get("/underwriting/{application_id}/decision")
async def get_decision(application_id: str) -> dict[str, Any]:
    """Retrieve the decision for an application."""
    records = audit_store.get_by_application(application_id)
    if not records:
        raise HTTPException(status_code=404, detail="No decision found for this application")
    latest = records[-1]
    return latest.get("final_decision", {})


@app.get("/underwriting/{application_id}/report")
async def get_report(application_id: str) -> dict[str, Any]:
    """Retrieve the audit trail for an application."""
    records = audit_store.get_by_application(application_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found for this application")
    return {"application_id": application_id, "audit_records": records}


# -------------------------------------------------------
# Document Ingestion Agent Endpoints
# -------------------------------------------------------


@app.post("/api/v1/ingest/upload-and-process", response_model=DocumentIngestionOutput)
async def upload_and_process_documents(
    application_id: str = Form("APP-2026-001"),
    borrower_id: str = Form("BORR-2026-001"),
    files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for ingestion.")

    temp_dir = tempfile.mkdtemp(prefix=f"mortgage_{application_id}_")
    saved_paths = []

    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_paths.append(file_path)

        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=saved_paths,
            application_id=application_id,
            borrower_id=borrower_id,
        )

        PROCESSED_APPLICATIONS[application_id] = output
        return output

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/v1/ingest/state/{application_id}", response_model=DocumentIngestionOutput)
async def get_ingestion_state(application_id: str):
    if application_id not in PROCESSED_APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application ID '{application_id}' not found.")
    return PROCESSED_APPLICATIONS[application_id]


@app.post("/api/v1/ingest/demo/{scenario_name}", response_model=DocumentIngestionOutput)
async def run_demo_scenario(
    scenario_name: str,
    application_id: Optional[str] = None,
):
    from tests.mock_data.generate_docs import generate_all_mock_scenarios

    scenarios = generate_all_mock_scenarios()
    scenario_map = {
        "clean": "clean_prime",
        "name_mismatch": "name_discrepancy",
        "salary_mismatch": "salary_discrepancy",
        "missing_docs": "missing_docs",
    }

    key = scenario_map.get(scenario_name.lower())
    if not key or key not in scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario '{scenario_name}'. Valid options: {list(scenario_map.keys())}",
        )

    app_id = application_id or f"APP-DEMO-{scenario_name.upper()}-2026"
    files = scenarios[key]

    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id=app_id,
        borrower_id=f"BORR-{scenario_name.upper()}-001",
    )

    PROCESSED_APPLICATIONS[app_id] = output
    return output


class HITLOverrideRequest(BaseModel):
    application_id: str
    field_path: str
    overridden_value: Any
    underwriter_notes: str
    underwriter_id: str = "UW-ADMIN-01"


class HITLOverrideResponse(BaseModel):
    status: str
    message: str
    application_id: str
    updated_field: str
    new_value: Any


@app.post("/api/v1/ingest/hitl/override", response_model=HITLOverrideResponse)
async def hitl_field_override(request: HITLOverrideRequest):
    if request.application_id not in PROCESSED_APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application '{request.application_id}' not found.")

    output = PROCESSED_APPLICATIONS[request.application_id]

    field_parts = request.field_path.split(".")
    target_obj = output

    try:
        for p in field_parts[:-1]:
            target_obj = getattr(target_obj, p)
        setattr(target_obj, field_parts[-1], request.overridden_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not apply override on path '{request.field_path}': {e}")

    output.audit_log.append(
        f"[HITL OVERRIDE by {request.underwriter_id}] Modified '{request.field_path}' to '{request.overridden_value}'. "
        f"Reason: {request.underwriter_notes}"
    )

    return HITLOverrideResponse(
        status="SUCCESS",
        message="Field override applied and recorded in audit log.",
        application_id=request.application_id,
        updated_field=request.field_path,
        new_value=request.overridden_value,
    )


# -------------------------------------------------------
# Property Valuation Agent Endpoints
# -------------------------------------------------------

import uuid
from app.models.property_valuation import PropertyIntake, ValuationResponse, ValuationRange
from app.graph.property_workflow import valuation_graph
from app.tools.external_api import fetch_api_valuation


@app.post("/api/v1/valuation/evaluate")
async def evaluate_property(intake: PropertyIntake):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {"property": intake.model_dump()}

    result = valuation_graph.invoke(initial_state, config=config)

    state = valuation_graph.get_state(config)

    if "explanation" in state.next or (result.get("human_review_required") and state.next):
        return {
            "status": "PENDING_HUMAN_REVIEW",
            "thread_id": thread_id,
            "message": "Valuation requires human review due to low confidence or high risk.",
            "current_confidence": result.get("confidence"),
            "risk_flags": result.get("risk_flags"),
        }

    return _build_valuation_response(result)


class ResumeRequest(BaseModel):
    approved: bool
    notes: str = ""


@app.post("/api/v1/valuation/{thread_id}/resume")
async def resume_valuation(thread_id: str, req: ResumeRequest):
    config = {"configurable": {"thread_id": thread_id}}
    state = valuation_graph.get_state(config)

    if not state.next:
        raise HTTPException(status_code=400, detail="Thread is not pending human review or does not exist.")

    if not req.approved:
        return {"status": "REJECTED", "message": "Valuation rejected by underwriter."}

    result = valuation_graph.invoke(None, config=config)

    return _build_valuation_response(result)


def _build_valuation_response(state_dict) -> dict:
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
        "explanation": state_dict.get("explanation", ""),
    }


@app.get("/api/mock-external/valuation")
async def mock_external_avm(locality: str, city: str, property_type: str, bhk: int, area_sqft: float):
    return fetch_api_valuation(locality, city, property_type, bhk, area_sqft)
