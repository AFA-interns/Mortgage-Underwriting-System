"""FOIR (Fixed Obligation to Income Ratio) and EMI calculations.

FOIR = (existing EMIs + credit-card EMI-equivalent + proposed EMI) / net
monthly income - the standard Indian bank underwriting DTI metric.
"""
from __future__ import annotations

from typing import Any

from app.credit.config import get_credit_config
from app.credit.employment import EmploymentBucket


def get_foir_threshold(employment_type: EmploymentBucket) -> float:
    thresholds = get_credit_config()["foir"]["thresholds"]
    return thresholds.get(employment_type, thresholds["self_employed"])


def calculate_emi(principal: float, annual_rate_percent: float, tenure_months: int) -> float:
    """Standard reducing-balance EMI formula. `annual_rate_percent` is a
    placeholder assumption (see
    credit_config.yaml::foir.assumed_annual_interest_rate_percent) - replace
    with the actual sanctioned rate once loan pricing reaches this agent."""
    if tenure_months <= 0:
        return 0.0
    monthly_rate = annual_rate_percent / 100 / 12
    if monthly_rate == 0:
        return round(principal / tenure_months, 2)
    factor = (1 + monthly_rate) ** tenure_months
    return round(principal * monthly_rate * factor / (factor - 1), 2)


def credit_card_emi_equivalent(credit_report: dict[str, Any]) -> float:
    """Per common Indian bank practice, an outstanding credit-card balance
    with no declared EMI still carries an EMI-equivalent obligation,
    approximated as the minimum-due percentage of the outstanding balance."""
    rate = get_credit_config()["foir"]["credit_card_emi_equivalent_rate"]
    outstanding = credit_report.get("credit_card_outstanding_total", 0.0) or 0.0
    return outstanding * rate


def calculate_monthly_obligations(
    declared_existing_emis: float,
    proposed_emi: float,
    credit_report: dict[str, Any],
) -> float:
    """The FOIR numerator - existing EMIs + credit-card equivalent + the EMI
    being applied for now."""
    return round(
        declared_existing_emis + proposed_emi + credit_card_emi_equivalent(credit_report), 2
    )


def calculate_foir(
    monthly_net_income: float,
    declared_existing_emis: float,
    proposed_emi: float,
    credit_report: dict[str, Any],
) -> float:
    if monthly_net_income <= 0:
        raise ValueError("monthly_net_income must be > 0 to compute FOIR")
    obligations = calculate_monthly_obligations(declared_existing_emis, proposed_emi, credit_report)
    return round(obligations / monthly_net_income, 4)
