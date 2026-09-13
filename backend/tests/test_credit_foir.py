"""Tests for FOIR and EMI calculations."""
import pytest

from app.credit.foir import (
    calculate_emi,
    calculate_foir,
    calculate_monthly_obligations,
    get_foir_threshold,
)


def test_foir_threshold_by_employment_type():
    assert get_foir_threshold("salaried") == 0.55
    assert get_foir_threshold("self_employed") == 0.45
    assert get_foir_threshold("business") == 0.45


def test_foir_threshold_unknown_defaults_to_self_employed():
    assert get_foir_threshold("something_else") == get_foir_threshold("self_employed")


def test_calculate_emi_zero_rate_is_flat():
    assert calculate_emi(120000, 0.0, 12) == pytest.approx(10000.0)


def test_calculate_emi_positive_and_decreases_with_longer_tenure():
    emi_short = calculate_emi(1000000, 8.5, 60)
    emi_long = calculate_emi(1000000, 8.5, 240)
    assert emi_short > 0
    assert emi_long > 0
    assert emi_long < emi_short


def test_calculate_emi_zero_tenure_is_zero():
    assert calculate_emi(1000000, 8.5, 0) == 0.0


def test_foir_includes_credit_card_min_due_as_emi_equivalent():
    foir = calculate_foir(
        monthly_net_income=100000,
        declared_existing_emis=10000,
        proposed_emi=20000,
        credit_report={"credit_card_outstanding_total": 100000},
    )
    # credit card equivalent = 100000 * 5% = 5000
    # total = 10000 + 20000 + 5000 = 35000; FOIR = 35000 / 100000 = 0.35
    assert foir == pytest.approx(0.35)


def test_monthly_obligations_matches_foir_numerator():
    obligations = calculate_monthly_obligations(10000, 20000, {"credit_card_outstanding_total": 100000})
    assert obligations == pytest.approx(35000)


def test_foir_raises_on_zero_income():
    with pytest.raises(ValueError):
        calculate_foir(0, 1000, 1000, {})
