"""Tests for input validator."""
from app.decision.input_validator import validate_inputs
from tests.conftest import get_good_case, get_missing_inputs_case


def test_good_case_is_complete():
    result = validate_inputs(get_good_case())
    assert result.is_complete is True
    assert len(result.missing_fields) == 0


def test_missing_inputs_detected():
    result = validate_inputs(get_missing_inputs_case())
    assert result.is_complete is False
    assert "credit_analysis" in result.missing_fields


def test_empty_case():
    result = validate_inputs({})
    assert result.is_complete is False
    assert "application_id" in result.missing_fields


def test_partial_missing():
    case = {
        "application_id": "TEST-001",
        "borrower_profile": {"name": "Test"},
        "document_analysis": {},
        "credit_analysis": None,
        "property_analysis": {"estimated_value": 0},
        "compliance_analysis": None,
    }
    result = validate_inputs(case)
    assert result.is_complete is False
    assert "credit_analysis" in result.missing_fields
    assert "compliance_analysis" in result.missing_fields


def test_warnings_for_zero_income():
    case = get_good_case()
    case["borrower_profile"]["monthly_income"] = 0
    result = validate_inputs(case)
    assert any("monthly_income" in w for w in result.warnings)
