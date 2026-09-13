"""Deterministic red-flag checks against the credit bureau report and the
declared loan details."""
from __future__ import annotations

from typing import Any

from app.credit.config import get_credit_config
from app.credit.employment import EmploymentBucket

# A red flag string is classified "severe" if it contains any of these
# markers (case-insensitive substring match). Kept as substrings (rather
# than a separate structured field) so `flags` can stay a plain list[str]
# per the shared CreditAnalysisResult contract, while decision/risk logic
# can still tell severity apart.
SEVERE_RED_FLAG_MARKERS = ("settled account", "written-off account", "dpd exceeding 90")


def detect_red_flags(
    employment_type: EmploymentBucket,
    monthly_net_income: float,
    requested_loan_amount: float,
    credit_report: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    cfg = get_credit_config()["red_flags"]

    settled = credit_report.get("settled_accounts", 0) or 0
    if settled > 0:
        flags.append(f"{settled} settled account(s) found in credit history")

    written_off = credit_report.get("written_off_accounts", 0) or 0
    if written_off > 0:
        flags.append(f"{written_off} written-off account(s) found in credit history")

    max_dpd = credit_report.get("max_dpd_last_12_months", 0) or 0
    if max_dpd > 90:
        flags.append(f"DPD exceeding 90 days in last 12 months (max DPD: {max_dpd})")

    enquiries = credit_report.get("recent_enquiries_last_90_days", 0) or 0
    if enquiries >= cfg["loan_stacking_enquiry_threshold"]:
        flags.append(f"Possible loan stacking - {enquiries} credit enquiries in last 90 days")

    multiples = cfg["income_to_loan_multiple"]
    multiple = multiples.get(employment_type, multiples["self_employed"])
    annual_income = monthly_net_income * 12
    if annual_income > 0 and requested_loan_amount > annual_income * multiple:
        flags.append(
            f"Requested loan amount (Rs.{requested_loan_amount:,.0f}) exceeds "
            f"{multiple}x annual income (Rs.{annual_income:,.0f}) - income-to-loan mismatch"
        )

    return flags


def count_severe_red_flags(red_flags: list[str]) -> int:
    lowered = [f.lower() for f in red_flags]
    return sum(1 for f in lowered if any(marker in f for marker in SEVERE_RED_FLAG_MARKERS))
