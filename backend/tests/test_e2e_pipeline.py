"""Synthetic end-to-end test — runs the full Decision Agent pipeline."""
from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from app.decision.finalizer import deterministic_finalize
from app.decision.report_writer import generate_report
from app.decision.risk_engine import calculate_risk_score
from app.models.decision import DecisionType, RiskLevel
from tests.conftest import get_good_case, get_missing_inputs_case, get_suspend_case, get_weak_case


def _full_pipeline(case):
    """Run the complete deterministic Decision Agent pipeline (no CrewAI)."""
    # 1. Validate
    from app.decision.input_validator import validate_inputs
    validated = validate_inputs(case)
    if not validated.is_complete:
        from app.models.decision import DecisionResult
        return DecisionResult(
            application_id=case.get("application_id", "UNKNOWN"),
            decision=DecisionType.SUSPEND,
            risk_score=0,
            risk_level=RiskLevel.VERY_HIGH,
            confidence=0,
            key_risk_factors=[f"Missing: {', '.join(validated.missing_fields)}"],
            human_review_required=True,
            rationale=f"Inputs incomplete: {validated.missing_fields}",
        ), None, None, None, None

    # 2. Contradictions
    contradictions = detect_contradictions(case)

    # 3. Compare
    comparison = compare_agents(case)

    # 4. Risk
    risk = calculate_risk_score(
        document=case.get("document_analysis", {}),
        credit=case.get("credit_analysis", {}),
        property_data=case.get("property_analysis", {}),
        compliance=case.get("compliance_analysis", {}),
        borrower=case.get("borrower_profile", {}),
    )

    # 5. Confidence
    confidence = calculate_confidence(case, contradictions, comparison)

    # 6. Finalize
    final = deterministic_finalize(
        case=case, risk=risk, confidence=confidence,
        contradictions=contradictions,
        compliance=case.get("compliance_analysis", {}),
    )

    # 7. Report
    report = generate_report(case, risk, confidence, None, final)

    return final, risk, confidence, contradictions, report


def test_good_case_pipeline():
    final, risk, confidence, _, report = _full_pipeline(get_good_case())
    assert final.application_id == "APP-001"
    assert final.decision in (DecisionType.APPROVE, DecisionType.SUSPEND)
    assert risk.score > 50
    assert confidence.score > 0.5
    assert len(report.positive_factors) > 0 or len(report.risk_factors) > 0


def test_weak_case_pipeline():
    final, risk, confidence, _, report = _full_pipeline(get_weak_case())
    assert final.decision != DecisionType.APPROVE
    assert risk.score < 50


def test_suspend_case_pipeline():
    final, risk, confidence, contradictions, _ = _full_pipeline(get_suspend_case())
    assert final.decision == DecisionType.SUSPEND
    assert any(c.severity.value in ("HIGH", "CRITICAL") for c in contradictions)


def test_missing_inputs_pipeline():
    final, *_ = _full_pipeline(get_missing_inputs_case())
    assert final.decision == DecisionType.SUSPEND
    assert final.human_review_required is True


def test_human_review_flag():
    final, *_ = _full_pipeline(get_suspend_case())
    assert final.human_review_required is True


def test_decision_has_rationale():
    for case_fn in [get_good_case, get_weak_case, get_suspend_case]:
        final, *_ = _full_pipeline(case_fn())
        assert isinstance(final.rationale, str)
        assert len(final.rationale) > 0


def test_decision_has_evidence():
    for case_fn in [get_good_case, get_weak_case]:
        final, *_ = _full_pipeline(case_fn())
        assert isinstance(final.evidence, list)


def test_critical_compliance_safety_gate():
    case = get_good_case()
    case["compliance_analysis"]["critical_flags"] = ["FRAUD_ALERT"]
    final, *_ = _full_pipeline(case)
    assert final.decision == DecisionType.SUSPEND
