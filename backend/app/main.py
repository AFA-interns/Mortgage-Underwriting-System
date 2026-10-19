"""FastAPI application — exposes underwriting API endpoints."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Response
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
    from app.services.applications import store as _store

    return {"status": "ok", "storage": _store.kind, "storage_detail": _store.description}



# -------------------------------------------------------
# Full-pipeline endpoints used by the frontend
# -------------------------------------------------------

from app.services.applications import (  # noqa: E402
    DEMO_SCENARIOS, get_parsed_document, materialize_image_paths, rerun_application,
    run_application, save_document_overrides, store,
)
from app.services.credit_bureau import declared_score_report  # noqa: E402
from app.document_ingestion.image_to_pdf import convert_image_to_pdf  # noqa: E402

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
    declared_cibil_score: Optional[int] = Form(None),
    bureau_consent: bool = Form(False),
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
        from tests.mock_data.generate_docs import (
            generate_all_mock_scenarios, generate_correctable_pan_scenario, generate_image_demo_documents,
        )

        generator = scenario.get("generator")
        if generator == "image_demo":
            raw_paths = generate_image_demo_documents()
        elif generator == "correctable_pan_error":
            raw_paths = generate_correctable_pan_scenario()
        else:
            raw_paths = generate_all_mock_scenarios()[scenario["key"]]
        paths, file_names = materialize_image_paths(raw_paths)
        return run_application(
            profile=dict(scenario["profile"]),
            file_paths=paths,
            file_names=file_names,
            bureau=scenario["bureau"],
            source=f"demo:{demo_scenario}",
        )

    uploads = [f for f in files if f.filename]
    if not uploads:
        raise HTTPException(400, "Upload at least one document (or choose a demo scenario).")
    allowed_ext = (".pdf", ".jpg", ".jpeg", ".png")
    bad = [f.filename for f in uploads if not f.filename.lower().endswith(allowed_ext)]
    if bad:
        raise HTTPException(400, f"Only PDF, JPG and PNG documents are supported. Rejected: {bad}")
    if not name.strip() or loan_amount <= 0 or monthly_income <= 0:
        raise HTTPException(400, "Borrower name, monthly income and loan amount are required.")
    bureau = None
    if declared_cibil_score is not None:
        try:
            bureau = declared_score_report(declared_cibil_score)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    tmp_dir = tempfile.mkdtemp(prefix="uw_upload_")
    try:
        paths: list[str] = []
        display_names: list[str] = []
        for i, upload in enumerate(uploads):
            dest = os.path.join(tmp_dir, f"{i:02d}_{os.path.basename(upload.filename)}")
            with open(dest, "wb") as out:
                shutil.copyfileobj(upload.file, out)
            if os.path.getsize(dest) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"'{upload.filename}' is larger than {MAX_UPLOAD_BYTES // 1_000_000} MB.")

            if dest.lower().endswith((".jpg", ".jpeg", ".png")):
                # Convert now so the stored document (and everything
                # downstream) is a real PDF, not a lying ".jpg" that's
                # actually PDF bytes.
                try:
                    dest = convert_image_to_pdf(dest)
                except Exception as exc:
                    raise HTTPException(400, f"Could not read '{upload.filename}' as an image: {exc}") from exc
                display_names.append(os.path.splitext(upload.filename)[0] + ".pdf")
            else:
                display_names.append(upload.filename)
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
            file_names=display_names,
            bureau=bureau,
            source="upload",
            bureau_consent=bureau_consent,
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


@app.get("/api/v1/applications/{application_id}/documents/{doc_id}/parsed")
def get_document_parsed_fields(application_id: str, doc_id: str) -> dict[str, Any]:
    """What this document's ingestion extracted (`extracted_fields`), any
    saved reviewer corrections (`overrides`), and the merge of the two
    (`effective_fields`) — what a /rerun would use. `editable_fields` is the
    whitelist the frontend's edit form should offer for this document type."""
    if store.get(application_id) is None:
        raise HTTPException(404, f"Application '{application_id}' not found.")
    payload = get_parsed_document(application_id, doc_id)
    if payload is None:
        raise HTTPException(404, "No parsed content for this document (not found, or nothing was extracted).")
    return payload


class DocumentFieldOverrides(BaseModel):
    overrides: Dict[str, Any]


@app.put("/api/v1/applications/{application_id}/documents/{doc_id}/parsed")
def put_document_parsed_fields(application_id: str, doc_id: str, body: DocumentFieldOverrides) -> dict[str, Any]:
    """Saves reviewer corrections for one document. Does not re-run the
    pipeline by itself — a reviewer can fix several documents first, then
    call POST .../rerun once."""
    if store.get(application_id) is None:
        raise HTTPException(404, f"Application '{application_id}' not found.")
    error = save_document_overrides(application_id, doc_id, body.overrides)
    if error is not None:
        raise HTTPException(400, error)
    return get_parsed_document(application_id, doc_id)


@app.post("/api/v1/applications/{application_id}/rerun")
def post_rerun_application(application_id: str) -> dict[str, Any]:
    """Re-runs the full pipeline for this application with any saved field
    overrides applied, updating this SAME application in place (same id,
    `rerun_count` incremented) - a document correction stays one case."""
    try:
        return rerun_application(application_id)
    except KeyError as exc:
        raise HTTPException(404, f"Application '{application_id}' not found.") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/v1/review-items")
def list_review_items() -> list[dict[str, Any]]:
    return store.review_items()


@app.post("/api/v1/review-items/{item_id}/resolve")
def resolve_review_item(item_id: str) -> dict[str, Any]:
    item = store.resolve_review_item(item_id)
    if item is None:
        raise HTTPException(404, f"Review item '{item_id}' not found.")
    return item


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


_SOURCE_LABELS = {
    "avnester": "AVnester",
    "scraped_db": "Scraped comparables database",
    "local_db": "Local comparables database",
    "none": "No source",
}


def _build_valuation_response(state_dict) -> dict:
    value_source = state_dict.get("value_source", "avnester")
    source_label = _SOURCE_LABELS.get(value_source, "AVnester")
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
        "value_source": value_source,
        "method": ["comparable_sales", value_source],
        "sources": ["Nominatim Geocoder", source_label],
        "explanation": state_dict.get("explanation", ""),
    }


@app.get("/api/mock-external/valuation")
async def mock_external_avm(locality: str, city: str, property_type: str, bhk: int, area_sqft: float):
    return fetch_api_valuation(locality, city, property_type, bhk, area_sqft)


# -------------------------------------------------------
# Decision Agent evaluation endpoints
# -------------------------------------------------------

from app.evaluation.evaluator import evaluate_cases, runtime_metrics_from_decisions  # noqa: E402
from app.evaluation.schemas import LabeledCase  # noqa: E402


class EvaluationRequest(BaseModel):
    cases: list[LabeledCase]


@app.post("/evaluation/report")
async def evaluation_report(request: EvaluationRequest) -> dict[str, Any]:
    """Compute full evaluation metrics over labeled cases.

    Predictions come from each case's ``predicted`` field when present,
    otherwise from audit history matched by application_id.
    """
    cases = request.cases
    for case in cases:
        if case.predicted is not None:
            continue
        records = audit_store.get_by_application(case.application_id)
        for record in reversed(records):
            final_decision = record.get("final_decision")
            if final_decision:
                case.predicted = DecisionResult.model_validate(final_decision)
                break
    missing = [c.application_id for c in cases if c.predicted is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"No prediction available for application_ids: {missing}",
        )
    report = evaluate_cases(cases)
    return report.model_dump(mode="json")


@app.get("/evaluation/runtime")
async def evaluation_runtime() -> dict[str, Any]:
    """Runtime/operational metrics over all audited decisions (no labels needed)."""
    decisions: list[DecisionResult] = []
    for record in audit_store.get_all():
        final_decision = record.get("final_decision")
        if final_decision:
            decisions.append(DecisionResult.model_validate(final_decision))
    return runtime_metrics_from_decisions(decisions).model_dump(mode="json")


# -------------------------------------------------------
# Per-agent metrics (frontend "Agent Metrics" page)
# -------------------------------------------------------
# Each agent is honest about what it can actually measure right now rather
# than reporting a number it doesn't have real data for - see
# AGENT_METRICS_STATUS below and DOCUMENT_INGESTION_METRICS.md / CREDIT_METRICS.md.

AGENT_METRICS_STATUS: list[dict[str, Any]] = [
    {
        "agent": "document_ingestion",
        "label": "Document Ingestion Agent",
        "status": "runnable",
        "description": (
            "Runs the real agent against this project's own 6 bundled demo "
            "scenarios (35 documents, hand-labeled ground truth) and computes "
            "classification, calibration, reconciliation, and operational metrics."
        ),
        "endpoint": "/api/v1/metrics/document-ingestion",
        "method": "POST",
    },
    {
        "agent": "decision",
        "label": "Decision Agent",
        "status": "runnable",
        "description": (
            "Runtime/operational metrics (decision mix, mean confidence, mean "
            "risk score) computed live from every decision this server has "
            "actually audited so far - no labels required. The audit log is "
            "in-memory and resets on server restart, so this can read 0 even "
            "when the Applications list (backed by Postgres) isn't empty."
        ),
        "endpoint": "/evaluation/runtime",
        "method": "GET",
    },
    {
        "agent": "credit",
        "label": "Credit Agent",
        "status": "runnable",
        "description": (
            "CREDIT_METRICS.md Phase 1 (bureau source mix, red-flag trigger "
            "rates, decision distribution, confidence-formula checks, Credit "
            "vs Decision agreement, upstream data-quality rate, adverse impact "
            "ratio) computed live from every application this server has "
            "stored - no outcome labels needed. Phase 2 (drift) needs two "
            "saved batches and Phase 3 (AUC/KS/bad-rate) needs closed-loan "
            "outcomes, neither of which this system captures yet, so those "
            "stay out of this report."
        ),
        "endpoint": "/api/v1/metrics/credit",
        "method": "POST",
    },
    {
        "agent": "property",
        "label": "Property Valuation Agent",
        "status": "runnable",
        "description": (
            "PROPERTY_VALUATION_METRICS.md Coverage Rate (share of stored "
            "applications for which a valuation was actually produced, "
            "broken down by source: AVnester / scraped DB / local median) "
            "computed live - no ground truth needed. PPE10/PPE20/MdAPE stay "
            "unavailable: they need each property's actual transaction "
            "price, which this system does not capture anywhere yet."
        ),
        "endpoint": "/api/v1/metrics/property",
        "method": "POST",
    },
    {
        "agent": "compliance",
        "label": "Compliance Agent",
        "status": "runnable",
        "description": (
            "Runs the real rules engine against a bundled, hand-labeled "
            "120-case golden set (KYC, identity, PMLA, RERA, NHB/PSL) and a "
            "60-pair name-matching set, and reports recall/precision/F1 "
            "plus rule-status, decision-gate, and confidence-formula "
            "agreement - deterministic, so no stored applications or "
            "outcome labels are needed. See compliance_eval/docs/"
            "metrics_spec.csv for the metric definitions."
        ),
        "endpoint": "/api/v1/metrics/compliance",
        "method": "POST",
    },
]


@app.get("/api/v1/metrics/overview")
async def agent_metrics_overview() -> list[dict[str, Any]]:
    """Which agents have a real, runnable benchmark right now, and which
    don't (with why) - lets the frontend render every agent honestly
    instead of only listing the ones that work.
    """
    return AGENT_METRICS_STATUS


@app.post("/api/v1/metrics/document-ingestion")
async def document_ingestion_metrics() -> dict[str, Any]:
    """Runs the real Document Ingestion Agent against this project's own
    bundled demo scenarios and returns the metrics report. Takes a few
    seconds (real PDF generation + OCR/parsing) - POST because it does
    real work, not a cached read.
    """
    from app.document_ingestion.benchmark import run_bundled_demo_benchmark

    return run_bundled_demo_benchmark()


@app.post("/api/v1/metrics/credit")
async def credit_metrics() -> dict[str, Any]:
    """CREDIT_METRICS.md Phase 1 report, computed live from every
    application this server currently has stored.
    """
    from app.credit.benchmark import run_phase1_report

    return run_phase1_report()


@app.post("/api/v1/metrics/property")
async def property_valuation_metrics() -> dict[str, Any]:
    """PROPERTY_VALUATION_METRICS.md Coverage Rate, computed live from
    every application this server currently has stored.
    """
    from app.property_valuation.benchmark import run_coverage_report

    return run_coverage_report()


@app.post("/api/v1/metrics/compliance")
async def compliance_metrics() -> dict[str, Any]:
    """Runs the real Compliance Agent against its bundled golden set and
    name-matching set and returns the metrics report. Deterministic rule
    engine - takes well under a second, but POST because it does real work,
    not a cached read.
    """
    from app.compliance.benchmark import run_compliance_benchmark

    return run_compliance_benchmark()
