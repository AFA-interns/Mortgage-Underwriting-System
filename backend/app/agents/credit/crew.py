"""Deterministic credit reasoning — explains the already-final rule-based credit assessment.

No LLM required. The task explicitly forbids proposing a different decision -
this only communicates the reasoning clearly.
"""
from __future__ import annotations

from typing import Any


def _build_credit_summary(borrower: dict[str, Any], credit_result: dict[str, Any]) -> str:
    """Build a structured text summary for the reasoning agent. Pulled out
    as its own function (like decision's _build_case_summary) so it can be
    unit-tested without invoking a real LLM."""
    return "\n".join(
        [
            f"Applicant: {borrower.get('name', 'N/A')} ({borrower.get('employment_type', 'N/A')})",
            f"Monthly Income: INR {borrower.get('monthly_income', 0):,.0f}",
            f"Loan Amount: INR {borrower.get('loan_amount', 0):,.0f} over "
            f"{borrower.get('loan_tenure_months', 0)} months",
            "",
            f"CIBIL Score: {credit_result.get('cibil_score') or 'No credit history (NA)'}",
            f"Credit Band: {credit_result.get('credit_band', 'N/A')}",
            f"FOIR: {credit_result.get('foir')}",
            f"LTV: {credit_result.get('ltv')}",
            f"Income Stability: {credit_result.get('income_stability', 'N/A')}",
            f"Red Flags: {credit_result.get('flags') or 'None'}",
            f"Composite Risk Score: {credit_result.get('risk_score', 'N/A')}/100",
            "Preliminary Decision (already final - explain, do not override): "
            f"{credit_result.get('preliminary_decision', 'N/A')}",
        ]
    )


def run_credit_reasoning(borrower: dict[str, Any], credit_result: dict[str, Any]) -> str:
    """Generate a deterministic plain-language explanation of the credit risk assessment.
    No LLM calls - purely rule-based explanation matching the deterministic
    credit analysis output."""
    cibil = credit_result.get('cibil_score')
    band = credit_result.get('credit_band', 'N/A')
    foir = credit_result.get('foir')
    ltv = credit_result.get('ltv')
    flags = credit_result.get('flags', [])
    risk_score = credit_result.get('risk_score', 'N/A')
    prelim = credit_result.get('preliminary_decision', 'N/A')

    parts = []

    if cibil is not None:
        parts.append(f"CIBIL score of {cibil} places the applicant in the {band} band.")
    else:
        parts.append("No credit history available; assessed as New-to-Credit.")

    if foir is not None:
        if foir > 0.5:
            parts.append(f"FOIR of {foir:.1%} exceeds typical thresholds, indicating high debt burden.")
        else:
            parts.append(f"FOIR of {foir:.1%} is within acceptable limits.")

    if ltv is not None:
        if ltv > 0.8:
            parts.append(f"LTV of {ltv:.1%} is high, limiting equity cushion.")
        else:
            parts.append(f"LTV of {ltv:.1%} provides adequate collateral coverage.")

    if flags:
        parts.append(f"Red flags detected: {', '.join(flags)}.")
    else:
        parts.append("No material red flags identified.")

    parts.append(f"Composite risk score: {risk_score}/100. Preliminary decision: {prelim}.")

    return " ".join(parts)