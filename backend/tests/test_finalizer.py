"""Tests for deterministic finalizer."""
from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from app.decision.finalizer import deterministic_finalize
from app.decision.risk_engine import calculate_risk_score
from app.models.decision import DecisionType
from tests.conftest import get_good_case, get_missing_inputs_case, get_suspend_case, get_weak_case


def _run_finalizer(case):
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    risk = calculate_risk_score(
        document=case.get("document_analysis", {}),
        credit=case.get("credit_analysis", {}),
        property_data=case.get("property_analysis", {}),
        compliance=case.get("compliance_analysis", {}),
        borrower=case.get("borrower_profile", {}),
    )
    confidence = calculate_confidence(case, contradictions, comparison)
    return deterministic_finalize(
        case=case, risk=risk, confidence=confidence,
        contradictions=contradictions,
        compliance=case.get("compliance_analysis", {}),
    )


def test_good_case_approve():
    result = _run_finalizer(get_good_case())
    # Good case should be APPROVE or SUSPEND (if confidence too low)
    assert result.decision in (DecisionType.APPROVE, DecisionType.SUSPEND)


def test_weak_case_not_approve():
    result = _run_finalizer(get_weak_case())
    assert result.decision != DecisionType.APPROVE


def test_missing_inputs_suspend():
    result = _run_finalizer(get_missing_inputs_case())
    assert result.decision == DecisionType.SUSPEND
    assert result.human_review_required is True


def test_safety_gate_critical_compliance():
    case = get_good_case()
    case["compliance_analysis"]["critical_flags"] = ["AML_ALERT"]
    result = _run_finalizer(case)
    assert result.decision == DecisionType.SUSPEND
    assert result.compliance_status == "BLOCKED"


def test_safety_gate_unresolved_contradiction():
    case = get_suspend_case()
    result = _run_finalizer(case)
    assert result.decision == DecisionType.SUSPEND


def test_always_has_rationale():
    result = _run_finalizer(get_good_case())
    assert len(result.rationale) > 0


def test_always_has_evidence():
    result = _run_finalizer(get_good_case())
    assert isinstance(result.evidence, list)
