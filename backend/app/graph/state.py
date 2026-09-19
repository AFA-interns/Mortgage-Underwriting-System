"""Shared LangGraph state for the mortgage underwriting workflow."""
from __future__ import annotations

from typing import Any, TypedDict


class UnderwritingState(TypedDict, total=False):
    application_id: str
    borrower_id: str
    borrower_profile: dict[str, Any]
    documents: list[dict[str, Any]]

    # Document Ingestion inputs
    raw_document_paths: list[str]

    # Upstream agent outputs
    document_analysis: dict[str, Any]
    doc_ingestion_output: dict[str, Any]
    credit_analysis: dict[str, Any]
    property_analysis: dict[str, Any]
    compliance_analysis: dict[str, Any]

    # Workflow control
    current_step: str
    status: str

    # Optional pre-fetched/synthetic credit bureau report, keyed by
    # application_id. When absent, app.graph.nodes.credit falls back to the
    # stubbed app.services.credit_bureau.fetch_credit_report. Lets tests and
    # a future real bureau integration bypass the stub without changing the
    # node's signature.
    credit_bureau_data: dict[str, Any]

    # Decision Agent internal results
    validation_result: dict[str, Any]
    contradictions: list[dict[str, Any]]
    agent_comparison: dict[str, Any]
    risk_assessment: dict[str, Any]
    confidence_assessment: dict[str, Any]
    decision_crew_output: dict[str, Any]

    # Final output
    decision: dict[str, Any]
    underwriting_report: dict[str, Any]
    human_review_required: bool
    audit_record: dict[str, Any]

    # Error tracking
    errors: list[dict[str, Any]]
