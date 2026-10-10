"""Deterministic (no-LLM) decision pipeline runner for offline evaluation."""
from __future__ import annotations

from typing import Any

from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from app.decision.finalizer import deterministic_finalize
from app.decision.input_validator import validate_inputs
from app.decision.risk_engine import calculate_risk_score
from app.models.decision import DecisionResult, DecisionType, RiskLevel


def run_deterministic_pipeline(case: dict[str, Any]) -> DecisionResult:
    """Run the deterministic decision path (validation → risk → confidence → finalizer).

    Mirrors the production LangGraph decision node minus the CrewAI reasoning step,
    so evaluation runs are fast, offline, and reproducible.
    """
    validated = validate_inputs(case)
    if not validated.is_complete:
        return DecisionResult(
            application_id=case.get("application_id", "UNKNOWN"),
            decision=DecisionType.SUSPEND,
            risk_score=0,
            risk_level=RiskLevel.VERY_HIGH,
            confidence=0.0,
            key_risk_factors=[f"Missing required inputs: {', '.join(validated.missing_fields)}"],
            human_review_required=True,
            rationale=f"Required inputs missing: {validated.missing_fields}",
            gate_triggered="missing_inputs",
        )

    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    risk = calculate_risk_score(
        document=case.get("document_analysis", {}),
        credit=case.get("credit_analysis", {}),
        property_data=case.get("property_analysis", {}),
        compliance=case.get("compliance_analysis", {}),
        borrower=case.get("borrower_profile", {}),
    )
    confidence = calculate_confidence(
        case=case, contradictions=contradictions, comparison=comparison
    )
    return deterministic_finalize(
        case=case,
        risk=risk,
        confidence=confidence,
        contradictions=contradictions,
        compliance=case.get("compliance_analysis", {}),
    )
