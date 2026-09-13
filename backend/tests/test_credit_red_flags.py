"""Tests for the deterministic red-flag checklist."""
from app.credit.red_flags import count_severe_red_flags, detect_red_flags


def test_settled_and_dpd_are_severe():
    flags = detect_red_flags(
        "salaried",
        50000,
        1000000,
        {"settled_accounts": 1, "max_dpd_last_12_months": 120},
    )
    assert any("settled" in f.lower() for f in flags)
    assert any("dpd" in f.lower() for f in flags)
    assert count_severe_red_flags(flags) == 2


def test_loan_stacking_flag():
    flags = detect_red_flags("salaried", 50000, 1000000, {"recent_enquiries_last_90_days": 4})
    assert any("loan stacking" in f.lower() for f in flags)


def test_income_to_loan_mismatch():
    # annual income = 240,000; salaried multiple = 6x -> cutoff 1,440,000
    flags = detect_red_flags("salaried", 20000, 5000000, {})
    assert any("income-to-loan mismatch" in f.lower() for f in flags)


def test_no_flags_for_clean_report():
    flags = detect_red_flags("salaried", 100000, 2000000, {})
    assert flags == []


def test_written_off_is_severe():
    flags = detect_red_flags("salaried", 50000, 1000000, {"written_off_accounts": 1})
    assert count_severe_red_flags(flags) == 1
