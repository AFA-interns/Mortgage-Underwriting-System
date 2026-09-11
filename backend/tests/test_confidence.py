"""Tests for confidence engine."""
from app.decision.agent_comparator import compare_agents
from app.decision.confidence import calculate_confidence
from app.decision.contradiction_detector import detect_contradictions
from tests.conftest import get_good_case, get_suspend_case


def test_good_case_above_threshold():
    case = get_good_case()
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    conf = calculate_confidence(case, contradictions, comparison)
    assert conf.score > 0.6
    assert "completeness" in conf.factors


def test_missing_inputs_low_confidence():
    case = get_suspend_case()
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    conf = calculate_confidence(case, contradictions, comparison)
    # With contradictions, confidence should be penalized
    assert conf.score < 0.9


def test_confidence_bounds():
    case = get_good_case()
    contradictions = detect_contradictions(case)
    comparison = compare_agents(case)
    conf = calculate_confidence(case, contradictions, comparison)
    assert 0 <= conf.score <= 1


def test_contradiction_reduces_confidence():
    case_a = get_good_case()
    case_b = get_good_case()
    case_b["document_analysis"]["contradictions"] = [
        {"field": "income", "severity": "HIGH", "sources": [], "resolution": "UNRESOLVED"}
    ]

    conf_a = calculate_confidence(case_a, detect_contradictions(case_a), compare_agents(case_a))
    conf_b = calculate_confidence(case_b, detect_contradictions(case_b), compare_agents(case_b))
    assert conf_b.score <= conf_a.score
