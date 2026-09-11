"""Shared LangGraph state for the mortgage underwriting workflow."""
from __future__ import annotations

from typing import Any, TypedDict


class UnderwritingState(TypedDict, total=False):
    application_id: str
    borrower_profile: dict[str, Any]
    documents: list[dict[str, Any]]

    # Upstream agent outputs
    document_analysis: dict[str, Any]
    credit_analysis: dict[str, Any]
    property_analysis: dict[str, Any]
    compliance_analysis: dict[str, Any]

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
