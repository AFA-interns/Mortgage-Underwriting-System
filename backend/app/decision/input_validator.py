"""Input validator — ensures all required upstream outputs are present and valid."""
from __future__ import annotations

from typing import Any

from app.models.decision import (
    ValidationResult,
)

REQUIRED_UPSTREAM_KEYS = [
    "borrower_profile",
    "document_analysis",
    "credit_analysis",
    "property_analysis",
    "compliance_analysis",
]


def validate_inputs(case: dict[str, Any]) -> ValidationResult:
    """Validate completeness and basic schema of all decision inputs."""
    missing_fields: list[str] = []
    warnings: list[str] = []
    upstream_status: dict[str, str] = {}

    if not case.get("application_id"):
        missing_fields.append("application_id")

    for key in REQUIRED_UPSTREAM_KEYS:
        val = case.get(key)
        if val is None or (isinstance(val, dict) and not val):
            missing_fields.append(key)
            upstream_status[key] = "MISSING"
        else:
            upstream_status[key] = "PRESENT"

    if "borrower_profile" in case and case["borrower_profile"]:
        bp = case["borrower_profile"]
        if not bp.get("name"):
            warnings.append("borrower_profile.name is empty")
        if bp.get("monthly_income", 0) <= 0:
            warnings.append("borrower_profile.monthly_income is not positive")
        if bp.get("loan_amount", 0) <= 0:
            warnings.append("borrower_profile.loan_amount is not positive")

    if "document_analysis" in case and case.get("document_analysis"):
        da = case["document_analysis"]
        missing_docs = da.get("missing_documents", [])
        if missing_docs:
            warnings.append(f"Missing documents: {', '.join(missing_docs)}")
        if da.get("missing_documents") and len(da.get("missing_documents", [])) > 3:
            warnings.append("Many documents missing — income/asset verification may be unreliable")

    if "credit_analysis" in case and case.get("credit_analysis"):
        ca = case["credit_analysis"]
        if ca.get("cibil_score") is not None and ca["cibil_score"] < 300:
            warnings.append("CIBIL score below expected range — possible data error")

    if "compliance_analysis" in case and case.get("compliance_analysis"):
        comp = case["compliance_analysis"]
        critical_flags = comp.get("critical_flags", [])
        if critical_flags:
            warnings.append(f"Compliance critical flags present: {critical_flags}")

    is_complete = len(missing_fields) == 0

    return ValidationResult(
        is_complete=is_complete,
        missing_fields=missing_fields,
        warnings=warnings,
        upstream_status=upstream_status,
    )
