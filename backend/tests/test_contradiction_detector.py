"""Tests for contradiction detector."""
from app.decision.contradiction_detector import detect_contradictions, has_unresolved_critical
from tests.conftest import get_good_case, get_suspend_case


def test_good_case_no_contradictions():
    contradictions = detect_contradictions(get_good_case())
    high = [c for c in contradictions if c.severity.value in ("HIGH", "CRITICAL")]
    assert len(high) == 0


def test_suspend_case_has_income_contradiction():
    contradictions = detect_contradictions(get_suspend_case())
    income_c = [c for c in contradictions if "income" in c.field.lower()]
    assert len(income_c) > 0
    assert has_unresolved_critical(contradictions) is True


def test_has_unresolved_critical_empty():
    assert has_unresolved_critical([]) is False


def test_detects_document_contradictions():
    case = get_good_case()
    case["document_analysis"]["contradictions"] = [
        {
            "field": "age",
            "severity": "MEDIUM",
            "sources": [{"agent": "aadhaar", "value": 32}, {"agent": "passport", "value": 35}],
            "resolution": "UNRESOLVED",
            "description": "Age mismatch",
        }
    ]
    contradictions = detect_contradictions(case)
    age_c = [c for c in contradictions if c.field == "age"]
    assert len(age_c) == 1


def test_property_value_mismatch():
    case = get_good_case()
    case["property_analysis"]["estimated_value"] = 5000000  # vs borrower 8000000
    contradictions = detect_contradictions(case)
    prop_c = [
        c for c in contradictions
        if "property" in c.field.lower() or "value" in c.field.lower()
    ]
    assert len(prop_c) > 0
