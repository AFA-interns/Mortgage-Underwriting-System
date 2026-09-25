"""NHB Directions & priority-sector eligibility check.

Populates ComplianceAnalysisResult.nhb. Informational only (never
CRITICAL) — it flags a classification mismatch, not a compliance
violation, so it never contributes to critical_flags or a SUSPEND.

NOTE: ceilings in compliance_config.yaml are Phase-1 placeholders — replace
with the exact NHB circular figures once sourced.
"""
from __future__ import annotations

from typing import Any

from app.models.decision import Severity

from .flags import RuleFlag


def check_nhb(data: dict[str, Any], config: dict) -> tuple[dict, list[RuleFlag]]:
    cfg = config.get("nhb_priority_sector", {})
    loan_meta = data.get("loan_meta", {})
    amount = loan_meta.get("loan_amount")
    tier = loan_meta.get("property_city_tier")

    if amount is None or tier is None:
        return {
            "status": "PASS",
            "priority_sector_eligible": None,
            "details": "Insufficient data to classify (loan amount or city tier missing).",
        }, []

    ceiling = cfg.get("metro_ceiling") if tier == "metro" else cfg.get("non_metro_ceiling")
    eligible = ceiling is None or amount <= ceiling
    flags: list[RuleFlag] = []

    if not eligible:
        flags.append(
            RuleFlag(
                code="NHB_PRIORITY_SECTOR_MISCLASSIFIED",
                severity=Severity.LOW,
                message=(
                    f"Loan amount {amount} exceeds the {tier} priority-sector "
                    f"housing loan ceiling ({ceiling})."
                ),
            )
        )

    return {
        "status": "PASS",  # informational category — never fails the check itself
        "priority_sector_eligible": eligible,
        "details": (
            "Eligible for priority-sector classification."
            if eligible
            else f"Not eligible: exceeds {tier} ceiling of {ceiling}."
        ),
    }, flags
