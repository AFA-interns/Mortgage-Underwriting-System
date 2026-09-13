"""Tests for CIBIL band mapping and risk-tier classification."""
from app.credit.cibil import get_credit_band, get_credit_risk_tier


def test_excellent_band():
    assert get_credit_band(780) == "Excellent"


def test_band_boundaries():
    assert get_credit_band(750) == "Excellent"
    assert get_credit_band(749) == "Good"
    assert get_credit_band(700) == "Good"
    assert get_credit_band(699) == "Fair"
    assert get_credit_band(550) == "Poor"
    assert get_credit_band(549) == "Very Poor"


def test_no_credit_history_is_not_very_poor():
    assert get_credit_band(None) == "New-to-Credit"


def test_out_of_range_score_is_clamped():
    assert get_credit_band(1000) == "Excellent"
    assert get_credit_band(0) == "Very Poor"


def test_risk_tier_mapping():
    assert get_credit_risk_tier("Excellent") == "low"
    assert get_credit_risk_tier("Good") == "low"
    assert get_credit_risk_tier("Fair") == "moderate"
    assert get_credit_risk_tier("Poor") == "high"
    assert get_credit_risk_tier("Very Poor") == "high"
    assert get_credit_risk_tier("New-to-Credit") == "moderate"
