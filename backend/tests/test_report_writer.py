"""Tests for report writer."""
from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from app.decision.finalizer import deterministic_finalize
from app.decision.report_writer import generate_report
from app.decision.risk_engine import calculate_risk_score
from tests.conftest import get_good_case


def test_report_generation():
    case = get_good_case()
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    risk = calculate_risk_score(
        document=case["document_analysis"],
        credit=case["credit_analysis"],
        property_data=case["property_analysis"],
        compliance=case["compliance_analysis"],
        borrower=case["borrower_profile"],
    )
    confidence = calculate_confidence(case, contradictions, comparison)
    final = deterministic_finalize(
        case=case, risk=risk, confidence=confidence,
        contradictions=contradictions,
        compliance=case["compliance_analysis"],
    )
    report = generate_report(case, risk, confidence, None, final)

    assert report.application_id == "APP-001"
    assert len(report.borrower_summary) > 0
    assert len(report.credit_assessment) > 0
    assert len(report.property_valuation) > 0
    assert "disclaimer" in report.model_fields
    assert report.disclaimer != ""


def test_report_does_not_alter_decision():
    case = get_good_case()
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    risk = calculate_risk_score(
        document=case["document_analysis"],
        credit=case["credit_analysis"],
        property_data=case["property_analysis"],
        compliance=case["compliance_analysis"],
        borrower=case["borrower_profile"],
    )
    confidence = calculate_confidence(case, contradictions, comparison)
    final = deterministic_finalize(
        case=case, risk=risk, confidence=confidence,
        contradictions=contradictions,
        compliance=case["compliance_analysis"],
    )
    report = generate_report(case, risk, confidence, None, final)
    assert report.decision == final.decision
