"""FastAPI application — exposes underwriting API endpoints."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, List, Optional, Dict

from app.services.avnester import search_properties

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Response
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
    raw_document_paths: list[str] = []
    borrower_profile: dict[str, Any] = {}
    document_analysis: dict[str, Any] = {}
    credit_analysis: dict[str, Any] = {}
    property_analysis: dict[str, Any] = {}
    compliance_analysis: dict[str, Any] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    from app.services.applications import store as _store

    return {"status": "ok", "storage": _store.kind, "storage_detail": _store.description}


# -------------------------------------------------------
# Full-pipeline endpoints used by the frontend
# -------------------------------------------------------

from app.services.applications import DEMO_SCENARIOS, run_application, store  # noqa: E402

MAX_UPLOAD_BYTES = 20_000_000


@app.get("/api/v1/demo-scenarios")
def list_demo_scenarios() -> list[dict[str, Any]]:
    return [
        {"id": sid, "label": s["label"], "description": s["description"], "profile": s["profile"]}
        for sid, s in DEMO_SCENARIOS.items()
    ]


@app.post("/api/v1/underwriting/run")
def run_full_pipeline(
    name: str = Form(""),
    monthly_income: float = Form(0),
    employment_type: str = Form("Salaried"),
    loan_amount: float = Form(0),
    loan_tenure_months: int = Form(240),
    property_value: float = Form(0),
    existing_debt: float = Form(0),
    demo_scenario: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    """Runs Document Ingestion -> Credit + Property + Compliance -> Decision.

    Either upload PDFs, or pass `demo_scenario` to use the bundled mock documents.
    """
    if demo_scenario:
        scenario = DEMO_SCENARIOS.get(demo_scenario)
        if scenario is None:
            raise HTTPException(400, f"Unknown demo scenario '{demo_scenario}'. Valid: {list(DEMO_SCENARIOS)}")
        from tests.mock_data.generate_docs import generate_all_mock_scenarios

        paths = generate_all_mock_scenarios()[scenario["key"]]
        return run_application(
            profile=dict(scenario["profile"]),
            file_paths=paths,
            file_names=[os.path.basename(p) for p in paths],
            bureau=scenario["bureau"],
            source=f"demo:{demo_scenario}",
        )

    uploads = [f for f in files if f.filename]
    if not uploads:
        raise HTTPException(400, "Upload at least one PDF document (or choose a demo scenario).")
    bad = [f.filename for f in uploads if not f.filename.lower().endswith(".pdf")]
    if bad:
        raise HTTPException(400, f"Only PDF documents are supported. Rejected: {bad}")
    if not name.strip() or loan_amount <= 0 or monthly_income <= 0:
        raise HTTPException(400, "Borrower name, monthly income and loan amount are required.")

    tmp_dir = tempfile.mkdtemp(prefix="uw_upload_")
    try:
        paths: list[str] = []
        for i, upload in enumerate(uploads):
            dest = os.path.join(tmp_dir, f"{i:02d}_{os.path.basename(upload.filename)}")
            with open(dest, "wb") as out:
                shutil.copyfileobj(upload.file, out)
            if os.path.getsize(dest) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"'{upload.filename}' is larger than {MAX_UPLOAD_BYTES // 1_000_000} MB.")
            paths.append(dest)

        profile = {
            "name": name.strip(),
            "monthly_income": monthly_income,
            "employment_type": employment_type,
            "loan_amount": loan_amount,
            "loan_tenure_months": loan_tenure_months,
            "property_value": property_value,
            "existing_debt": existing_debt,
        }
        return run_application(
            profile=profile,
            file_paths=paths,
            file_names=[u.filename for u in uploads],
            source="upload",
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/v1/applications")
def list_applications() -> list[dict[str, Any]]:
    return store.list()


@app.get("/api/v1/applications/{application_id}")
def get_application(application_id: str) -> dict[str, Any]:
    view = store.get(application_id)
    if view is None:
        raise HTTPException(404, f"Application '{application_id}' not found.")
    return view


@app.get("/api/v1/applications/{application_id}/documents/{doc_id}")
def get_application_document(application_id: str, doc_id: str) -> Response:
    """Serves a stored source PDF inline so reviewers can open it in the browser."""
    found = store.get_document(application_id, doc_id)
    if found is None:
        raise HTTPException(404, "Document not found.")
    filename, content = found
    safe = filename.encode("ascii", "ignore").decode() or "document.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe}"'},
    )


@app.get("/api/v1/review-items")
def list_review_items() -> list[dict[str, Any]]:
    return store.review_items()


@app.post("/api/v1/review-items/{item_id}/resolve")
def resolve_review_item(item_id: str) -> dict[str, Any]:
    item = store.resolve_review_item(item_id)
    if item is None:
        raise HTTPException(404, f"Review item '{item_id}' not found.")
    return item


@app.post("/underwriting/{application_id}/run")
async def run_underwriting(application_id: str, request: UnderwritingRequest) -> dict[str, Any]:
    """Run the full Decision Agent pipeline."""
    state: UnderwritingState = {
        "application_id": application_id,
        "raw_document_paths": request.raw_document_paths,
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

@app.post("/property/search")
def property_search(filters: dict[str, Any]):
    """Test endpoint for AVnester API connection."""
    return search_properties(filters)

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

    # The graph always pauses before "explanation"; only surface that pause
    # to the underwriter when the valuation actually needs human review.
    if state.next and not result.get("human_review_required"):
        result = valuation_graph.invoke(None, config=config)
        return _build_valuation_response(result)

    if state.next:
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
        "method": ["comparable_sales", "avnester"],
        "sources": ["Nominatim Geocoder", "AVnester"],
        "explanation": state_dict.get("explanation", ""),
    }


@app.get("/api/mock-external/valuation")
async def mock_external_avm(locality: str, city: str, property_type: str, bhk: int, area_sqft: float):
    return fetch_api_valuation(locality, city, property_type, bhk, area_sqft)
