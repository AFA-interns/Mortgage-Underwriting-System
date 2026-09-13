"""Tests for deterministic risk engine."""
from app.decision.risk_engine import calculate_risk_score
from app.models.decision import RiskLevel
from tests.conftest import get_good_case, get_weak_case


def test_good_case_high_score():
    case = get_good_case()
    risk = calculate_risk_score(
        document=case["document_analysis"],
        credit=case["credit_analysis"],
        property_data=case["property_analysis"],
        compliance=case["compliance_analysis"],
        borrower=case["borrower_profile"],
    )
    assert risk.score >= 75
    assert risk.level in (RiskLevel.LOW, RiskLevel.MODERATE)
    assert risk.calculation_failed is False
    assert len(risk.components) == 6


def test_weak_case_low_score():
    case = get_weak_case()
    risk = calculate_risk_score(
        document=case["document_analysis"],
        credit=case["credit_analysis"],
        property_data=case["property_analysis"],
        compliance=case["compliance_analysis"],
        borrower=case["borrower_profile"],
    )
    assert risk.score < 50
    assert risk.level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)


def test_score_bounds():
    risk = calculate_risk_score(
        document={},
        credit={},
        property_data={},
        compliance={},
        borrower={},
    )
    assert 0 <= risk.score <= 100


def test_components_sum_to_total():
    case = get_good_case()
    risk = calculate_risk_score(
        document=case["document_analysis"],
        credit=case["credit_analysis"],
        property_data=case["property_analysis"],
        compliance=case["compliance_analysis"],
        borrower=case["borrower_profile"],
    )
    total_weighted = sum(c.weighted_score for c in risk.components)
    assert abs(total_weighted - risk.score) < 0.5


def test_weights_sum_to_one():
    from app.decision.risk_engine import _load_config
    config = _load_config()
    weights = config["risk"]["weights"]
    assert abs(sum(weights.values()) - 1.0) < 0.01
