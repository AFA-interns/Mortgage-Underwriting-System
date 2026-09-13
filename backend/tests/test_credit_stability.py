"""Tests for income stability classification."""
from app.credit.stability import assess_income_stability


def test_salaried_clean_is_stable():
    assert assess_income_stability("salaried", []) == "stable"


def test_salaried_with_severe_flag_is_unstable():
    flags = ["1 settled account(s) found in credit history"]
    assert assess_income_stability("salaried", flags) == "unstable"


def test_self_employed_clean_is_moderately_stable():
    assert assess_income_stability("self_employed", []) == "moderately_stable"


def test_business_with_severe_flag_is_unstable():
    flags = ["DPD exceeding 90 days in last 12 months (max DPD: 120)"]
    assert assess_income_stability("business", flags) == "unstable"
