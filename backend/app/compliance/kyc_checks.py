"""KYC / CDD completeness check.

Populates ComplianceAnalysisResult.kyc_cdd. An incomplete KYC file always
produces a CRITICAL flag — per the design report, this must never allow an
automated Approve (enforced downstream by the Decision Agent's finalizer
Gate #1, which SUSPENDs on any non-empty critical_flags).
"""
from __future__ import annotations

from typing import Any

from app.models.decision import Severity

from .flags import RuleFlag


def check_kyc_cdd(data: dict[str, Any], config: dict) -> tuple[dict, list[RuleFlag]]:
    required = set(config.get("required_kyc_documents", []))
    docs_by_type = {d.get("doc_type"): d for d in data.get("kyc_documents", [])}

    missing: list[str] = []
    flags: list[RuleFlag] = []

    for doc_type in required:
        doc = docs_by_type.get(doc_type)
        if doc is None or not doc.get("present", False):
            missing.append(doc_type)
            flags.append(
                RuleFlag(
                    code="KYC_INCOMPLETE",
                    severity=Severity.CRITICAL,
                    message=f"Required KYC document '{doc_type}' was not submitted.",
                )
            )
        elif not doc.get("valid", True) or not doc.get("readable", True):
            missing.append(doc_type)
            reason = "not valid" if not doc.get("valid", True) else "not readable"
            flags.append(
                RuleFlag(
                    code="KYC_INCOMPLETE",
                    severity=Severity.CRITICAL,
                    message=f"KYC document '{doc_type}' is {reason}.",
                )
            )

    status = "FAIL" if missing else "PASS"
    return {"status": status, "missing_documents": missing}, flags
