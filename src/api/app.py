"""
FastAPI REST API for Document Ingestion Agent.
Enables frontend developers and downstream microservices to:
- Upload borrower document packages
- Run full 7-step Ingestion & Reconciliation Pipeline
- Query extracted entities, confidence, and audit trail
- Trigger Human-in-the-Loop (HITL) field overrides
- Run 1-click built-in demo scenarios
"""

import os
import shutil
import tempfile
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.document_ingestion.agent import DocumentIngestionAgent, document_ingestion_node
from src.mock_data.generate_docs import generate_all_mock_scenarios
from src.models.state import DocumentIngestionOutput, MortgageUnderwritingState

app = FastAPI(
    title="India Mortgage Underwriting System - Document Ingestion API",
    description="Agentic AI API for automated ingestion, OCR extraction, field validation, and cross-document reconciliation of Indian home loan applications.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session cache for processed application packages
PROCESSED_APPLICATIONS: Dict[str, DocumentIngestionOutput] = {}


class HITLOverrideRequest(BaseModel):
    application_id: str
    field_path: str  # e.g., "borrower_kyc.primary_name" or "borrower_income.monthly_gross_salary"
    overridden_value: Any
    underwriter_notes: str
    underwriter_id: str = "UW-ADMIN-01"


class HITLOverrideResponse(BaseModel):
    status: str
    message: str
    application_id: str
    updated_field: str
    new_value: Any


@app.get("/")
def root():
    return {
        "service": "Agentic AI Home Loan Underwriting - Document Ingestion Agent",
        "agent_owner": "Tejasva",
        "jurisdiction": "India (FNMA/FHLMC & RBI Compliant)",
        "docs_url": "/docs",
        "status": "HEALTHY",
    }


@app.post("/api/v1/ingest/upload-and-process", response_model=DocumentIngestionOutput)
async def upload_and_process_documents(
    application_id: str = Form("APP-2026-001"),
    borrower_id: str = Form("BORR-2026-001"),
    files: List[UploadFile] = File(...),
):
    """
    Uploads a multi-file borrower document bundle (PDFs/Images) and runs the 7-step Ingestion Pipeline.
    """
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
        # Cleanup temporary upload folder
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/v1/ingest/state/{application_id}", response_model=DocumentIngestionOutput)
def get_ingestion_state(application_id: str):
    """
    Retrieves the processed Document Ingestion output state for downstream agents or frontend dashboard.
    """
    if application_id not in PROCESSED_APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application ID '{application_id}' not found.")
    return PROCESSED_APPLICATIONS[application_id]


@app.post("/api/v1/ingest/demo/{scenario_name}", response_model=DocumentIngestionOutput)
def run_demo_scenario(
    scenario_name: str,
    application_id: Optional[str] = None,
):
    """
    Executes one of the built-in mock scenarios:
    - `clean`: Prime Salaried Borrower (Aarav Sharma - TCS)
    - `name_mismatch`: Name Discrepancy Case (Priya Suresh Patel vs Priya S Patel)
    - `salary_mismatch`: Income Discrepancy Case (Vikram Malhotra - ₹1.6L vs ₹85k)
    - `missing_docs`: Missing Mandatory Documents Case (Rahul Verma)
    """
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
            detail=f"Invalid scenario '{scenario_name}'. Valid options: {list(scenario_map.keys())}"
        )

    app_id = application_id or f"APP-DEMO-{scenario_name.upper()}-2026"
    files = scenarios[key]

    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id=app_id,
        borrower_id=f"BORR-{scenario_name.upper()}-001"
    )

    PROCESSED_APPLICATIONS[app_id] = output
    return output


@app.post("/api/v1/ingest/hitl/override", response_model=HITLOverrideResponse)
def hitl_field_override(request: HITLOverrideRequest):
    """
    Allows a human underwriter to override flagged fields during Human-in-the-Loop review.
    """
    if request.application_id not in PROCESSED_APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application '{request.application_id}' not found.")

    output = PROCESSED_APPLICATIONS[request.application_id]
    
    # Apply override dynamically on structured profiles
    field_parts = request.field_path.split(".")
    target_obj = output
    
    try:
        for p in field_parts[:-1]:
            target_obj = getattr(target_obj, p)
        setattr(target_obj, field_parts[-1], request.overridden_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not apply override on path '{request.field_path}': {str(e)}")

    output.audit_log.append(
        f"[HITL OVERRIDE by {request.underwriter_id}] Modified '{request.field_path}' to '{request.overridden_value}'. Reason: {request.underwriter_notes}"
    )

    return HITLOverrideResponse(
        status="SUCCESS",
        message="Field override applied and recorded in audit log.",
        application_id=request.application_id,
        updated_field=request.field_path,
        new_value=request.overridden_value,
    )
