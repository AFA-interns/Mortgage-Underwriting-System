"""Loan-to-Value ratio using the borrower-declared property value.

This is a preliminary LTV check by the Credit Analysis Agent, using the
declared `property_value` on BorrowerProfile - not the authoritative
valuation, which comes later from the Property Valuation Agent
(property_analysis.estimated_value). The Decision Agent's risk engine and
contradiction detector cross-check the two.
"""
from __future__ import annotations


def calculate_ltv(loan_amount: float, property_value: float) -> float | None:
    if property_value <= 0:
        return None
    return round(loan_amount / property_value, 4)
