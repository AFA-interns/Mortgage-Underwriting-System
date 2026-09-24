"""KYC / PMLA (Anti-Money Laundering) check.

Populates ComplianceAnalysisResult.pmla_source_of_funds.
"""
from __future__ import annotations

from typing import Any

from app.models.decision import Severity

from .flags import RuleFlag


def check_pmla_source_of_funds(
    data: dict[str, Any], config: dict
) -> tuple[dict, list[RuleFlag]]:
    cfg = config.get("pmla_aml", {})
    pmla = data.get("pmla", {})
    flags: list[RuleFlag] = []

    source_declared = bool(pmla.get("source_of_funds_declared", False))
    identity_logged = bool(pmla.get("identity_verification_logged", False))

    if cfg.get("require_source_of_funds_declaration", True) and not source_declared:
        flags.append(
            RuleFlag(
                code="PMLA_SOURCE_OF_FUNDS_MISSING",
                severity=Severity.CRITICAL,
                message="Source-of-funds declaration is missing or not logged.",
            )
        )

    if cfg.get("require_identity_verification_log", True) and not identity_logged:
        flags.append(
            RuleFlag(
                code="PMLA_IDENTITY_LOG_MISSING",
                severity=Severity.MEDIUM,
                message="Identity verification was not logged prior to recommendation.",
            )
        )

    status = "FAIL" if any(f.severity == Severity.CRITICAL for f in flags) else (
        "WARNING" if flags else "PASS"
    )
    return {
        "status": status,
        "source_of_funds_declared": source_declared,
        "identity_verification_logged": identity_logged,
    }, flags
