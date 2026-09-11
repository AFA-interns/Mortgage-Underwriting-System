"""Tests for agent comparator."""
from app.decision.agent_comparator import compare_agents
from tests.conftest import get_good_case, get_suspend_case


def test_good_case_agrees_on_income():
    comparison = compare_agents(get_good_case())
    assert "monthly_income" in comparison.agreement_fields


def test_suspend_case_disagrees_on_income():
    comparison = compare_agents(get_suspend_case())
    assert "monthly_income" in comparison.disagreement_fields
    assert comparison.material_disagreement is True


def test_confidence_comparison_keys():
    comparison = compare_agents(get_good_case())
    assert "credit" in comparison.confidence_comparison
    assert "property" in comparison.confidence_comparison


def test_assessments_compared():
    comparison = compare_agents(get_good_case())
    assert set(comparison.assessments_compared) == {"credit", "property", "compliance", "document"}
