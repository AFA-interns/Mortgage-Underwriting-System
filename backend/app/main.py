"""FastAPI application — exposes underwriting API endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.graph.state import UnderwritingState
from app.graph.workflow import build_underwriting_graph
from app.models.decision import DecisionResult
from app.services.audit import audit_store, create_audit_record

app = FastAPI(
    title="Mortgage Underwriting API",
    description="Agentic AI Mortgage Underwriting Decision Agent",
    version="0.1.0",
)


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
