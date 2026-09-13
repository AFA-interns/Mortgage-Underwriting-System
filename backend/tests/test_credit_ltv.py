"""Tests for the preliminary LTV calculation."""
from app.credit.ltv import calculate_ltv


def test_ltv_basic():
    assert calculate_ltv(5000000, 8000000) == 0.625


def test_ltv_none_when_no_property_value():
    assert calculate_ltv(5000000, 0) is None
    assert calculate_ltv(5000000, -100) is None
