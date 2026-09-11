"""LangGraph decision node — orchestrates the full decision agent pipeline."""
from __future__ import annotations

from typing import Any

from app.agents.decision.crew import run_decision_crew
from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from app.decision.finalizer import deterministic_finalize
from app.decision.input_validator import validate_inputs
from app.decision.report_writer import generate_report
from app.decision.risk_engine import calculate_risk_score
from app.graph.state import UnderwritingState
from app.models.decision import DecisionResult


def decision_node(state: UnderwritingState) -> dict[str, Any]:
    """LangGraph node that runs the complete Decision Agent pipeline."""
    errors: list[dict[str, Any]] = []

    # 1. Validate inputs
    validated = validate_inputs(state)
    validation_dict = validated.model_dump()

    if not validated.is_complete:
        # Cannot proceed — required data missing
        from app.models.decision import DecisionType, RiskLevel

        decision = DecisionResult(
            application_id=state.get("application_id", "UNKNOWN"),
            decision=DecisionType.SUSPEND,
            risk_score=0,
            risk_level=RiskLevel.VERY_HIGH,
            confidence=0,
            key_risk_factors=[f"Missing required inputs: {', '.join(validated.missing_fields)}"],
            human_review_required=True,
            rationale=f"Required inputs missing: {validated.missing_fields}",
        )
        return {
            "validation_result": validation_dict,
            "decision": decision.model_dump(),
            "human_review_required": True,
            "errors": [{"stage": "validation", "message": f"Missing: {validated.missing_fields}"}],
        }

    # 2. Detect contradictions
    contradictions = detect_contradictions(state)
    contradictions_dicts = [c.model_dump() for c in contradictions]

    # 3. Compare agents
    comparison = compare_agents(state)
    comparison_dict = comparison.model_dump()

    # 4. Risk scoring
    risk = calculate_risk_score(
        document=state.get("document_analysis", {}),
        credit=state.get("credit_analysis", {}),
        property_data=state.get("property_analysis", {}),
        compliance=state.get("compliance_analysis", {}),
        borrower=state.get("borrower_profile", {}),
    )
    risk_dict = risk.model_dump()

    # 5. Confidence
    confidence = calculate_confidence(
        case=state,
        contradictions=contradictions,
        comparison=comparison,
    )
    confidence_dict = confidence.model_dump()

    # 6. CrewAI Decision Crew
    crew_result = run_decision_crew(
        case=state,
        risk=risk_dict,
        confidence=confidence_dict,
        contradictions=contradictions_dicts,
    )
    crew_dict = crew_result.model_dump()

    # 7. Deterministic finalization
    final = deterministic_finalize(
        case=state,
        risk=risk,
        confidence=confidence,
        contradictions=contradictions,
        compliance=state.get("compliance_analysis", {}),
        crew_result=crew_result,
    )
    final_dict = final.model_dump()

    # 8. Report
    report = generate_report(
        case=state,
        risk=risk,
        confidence=confidence,
        crew_result=crew_result,
        final_decision=final,
    )
    report_dict = report.model_dump()

    return {
        "validation_result": validation_dict,
        "contradictions": contradictions_dicts,
        "agent_comparison": comparison_dict,
        "risk_assessment": risk_dict,
        "confidence_assessment": confidence_dict,
        "decision_crew_output": crew_dict,
        "decision": final_dict,
        "underwriting_report": report_dict,
        "human_review_required": final.human_review_required,
        "errors": errors,
    }
