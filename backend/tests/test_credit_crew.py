"""Tests for the Credit reasoning summary builder (no real LLM call - mirrors
tests/test_crew.py's approach for the Decision Agent's crew)."""
from app.agents.credit.crew import _build_credit_summary


def test_summary_contains_key_fields():
    borrower = {
        "name": "Priya Sharma",
        "employment_type": "salaried",
        "monthly_income": 150000,
        "loan_amount": 5000000,
        "loan_tenure_months": 240,
    }
    credit_result = {
        "cibil_score": 780,
        "credit_band": "Excellent",
        "foir": 0.25,
        "ltv": 0.625,
        "income_stability": "stable",
        "flags": [],
        "risk_score": 91.5,
        "preliminary_decision": "APPROVE",
    }
    summary = _build_credit_summary(borrower, credit_result)
    assert "Priya Sharma" in summary
    assert "CIBIL Score: 780" in summary
    assert "Excellent" in summary
    assert "APPROVE" in summary


def test_summary_handles_no_credit_history():
    summary = _build_credit_summary({}, {"cibil_score": None, "flags": []})
    assert "No credit history (NA)" in summary
