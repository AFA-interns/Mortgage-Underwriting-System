from __future__ import annotations

import operator
from typing import Any, Annotated, TypedDict


class UnderwritingState(TypedDict, total=False):
    application_id: str
    borrower_id: str
    borrower_profile: dict[str, Any]
    documents: list[dict[str, Any]]
    raw_document_paths: list[str]

    document_analysis: dict[str, Any]
    doc_ingestion_output: dict[str, Any]
    credit_analysis: dict[str, Any]
    property_analysis: dict[str, Any]
    compliance_analysis: dict[str, Any]

    current_step: str
    status: str

    credit_bureau_data: dict[str, Any]

    validation_result: dict[str, Any]
    contradictions: list[dict[str, Any]]
    agent_comparison: dict[str, Any]
    risk_assessment: dict[str, Any]
    confidence_assessment: dict[str, Any]
    decision_crew_output: dict[str, Any]

    decision: dict[str, Any]
    underwriting_report: dict[str, Any]
    human_review_required: bool
    audit_record: dict[str, Any]

    errors: Annotated[list[dict[str, Any]], operator.add]
