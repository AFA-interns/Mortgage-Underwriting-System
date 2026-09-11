"""Contradiction detector — identifies field-level conflicts between agent outputs."""
from __future__ import annotations

from typing import Any

from app.models.decision import Contradiction, ResolutionStatus, Severity

# Fields to cross-check between document analysis and credit analysis
_INCOME_FIELDS = [
    ("document_analysis.income.monthly_income", "credit_analysis.raw_data.monthly_income"),
    ("borrower_profile.monthly_income", "credit_analysis.raw_data.monthly_income"),
]

_PROPERTY_FIELDS = [
    ("property_analysis.estimated_value", "borrower_profile.property_value"),
    ("property_analysis.estimated_value", "credit_analysis.raw_data.property_value"),
]

_LTV_FIELDS = [
    ("credit_analysis.ltv", "borrower_profile.loan_amount / borrower_profile.property_value"),
]

_CIBIL_FIELDS = [
    ("borrower_profile.cibil_score", "credit_analysis.cibil_score"),
]


def _resolve_path(data: dict[str, Any], path: str) -> Any:
    """Retrieve a value from nested dict using dot-separated path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _check_numeric_match(
    val_a: Any, val_b: Any, tolerance_percent: float = 10.0
) -> tuple[bool, float]:
    """Check if two numeric values match within tolerance. Returns (match, diff_percent)."""
    if val_a is None or val_b is None:
        return True, 0.0
    try:
        a, b = float(val_a), float(val_b)
    except (TypeError, ValueError):
        return True, 0.0
    if a == 0 and b == 0:
        return True, 0.0
    base = max(abs(a), abs(b))
    if base == 0:
        return True, 0.0
    diff_percent = abs(a - b) / base * 100
    return diff_percent <= tolerance_percent, diff_percent


def detect_contradictions(
    case: dict[str, Any],
    income_tolerance: float = 10.0,
    value_tolerance: float = 5.0,
) -> list[Contradiction]:
    """Detect contradictions across upstream agent outputs."""
    contradictions: list[Contradiction] = []

    # Check income fields
    for doc_path, credit_path in _INCOME_FIELDS:
        doc_val = _resolve_path(case, doc_path)
        credit_val = _resolve_path(case, credit_path)
        if doc_val is not None and credit_val is not None:
            match, diff = _check_numeric_match(doc_val, credit_val, income_tolerance)
            if not match:
                severity = Severity.HIGH if diff > 30 else Severity.MEDIUM
                contradictions.append(
                    Contradiction(
                        field=doc_path.split(".")[-1],
                        severity=severity,
                        sources=[
                            {"agent": "document", "path": doc_path, "value": doc_val},
                            {"agent": "credit", "path": credit_path, "value": credit_val},
                        ],
                        resolution=ResolutionStatus.UNRESOLVED,
                        description=f"Income mismatch: {diff:.1f}% difference",
                    )
                )

    # Check property value fields
    for path_a, path_b in _PROPERTY_FIELDS:
        val_a = _resolve_path(case, path_a)
        val_b = _resolve_path(case, path_b)
        if val_a is not None and val_b is not None:
            match, diff = _check_numeric_match(val_a, val_b, value_tolerance)
            if not match:
                severity = Severity.HIGH if diff > 20 else Severity.MEDIUM
                contradictions.append(
                    Contradiction(
                        field=path_a.split(".")[-1],
                        severity=severity,
                        sources=[
                            {"agent": "property", "path": path_a, "value": val_a},
                            {"agent": "borrower", "path": path_b, "value": val_b},
                        ],
                        resolution=ResolutionStatus.UNRESOLVED,
                        description=f"Property value mismatch: {diff:.1f}% difference",
                    )
                )

    # Check CIBIL score
    for doc_path, credit_path in _CIBIL_FIELDS:
        doc_val = _resolve_path(case, doc_path)
        credit_val = _resolve_path(case, credit_path)
        if doc_val is not None and credit_val is not None:
            match, diff = _check_numeric_match(doc_val, credit_val, 5.0)
            if not match:
                contradictions.append(
                    Contradiction(
                        field="cibil_score",
                        severity=Severity.HIGH,
                        sources=[
                            {"agent": "borrower", "path": doc_path, "value": doc_val},
                            {"agent": "credit", "path": credit_path, "value": credit_val},
                        ],
                        resolution=ResolutionStatus.UNRESOLVED,
                        description=f"CIBIL score mismatch: {diff:.1f}% difference",
                    )
                )

    # Check document-reported contradictions
    doc_analysis = case.get("document_analysis", {})
    for dc in doc_analysis.get("contradictions", []):
        contradictions.append(
            Contradiction(
                field=dc.get("field", "unknown"),
                severity=Severity(dc.get("severity", "MEDIUM")),
                sources=dc.get("sources", []),
                resolution=ResolutionStatus(dc.get("resolution", "UNRESOLVED")),
                description=dc.get("description", ""),
            )
        )

    return contradictions


def has_unresolved_critical(contradictions: list[Contradiction]) -> bool:
    """Check if any HIGH/CRITICAL severity contradiction is still unresolved."""
    return any(
        c.severity in (Severity.HIGH, Severity.CRITICAL)
        and c.resolution == ResolutionStatus.UNRESOLVED
        for c in contradictions
    )
