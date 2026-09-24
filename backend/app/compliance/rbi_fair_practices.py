"""RBI Fair Practices Code adherence check.

Populates ComplianceAnalysisResult.rbi_fair_practices. Defensive guard
only: protected attributes must never appear as keys used in per-decision
logic (Architectural Invariant #10 in README_decision.md). Aggregate
fairness monitoring is a separate batch job, out of scope for this
real-time node.
"""
from __future__ import annotations

from typing import Any

from app.models.decision import Severity

from .flags import RuleFlag


def check_rbi_fair_practices(
    data: dict[str, Any], config: dict
) -> tuple[dict, list[RuleFlag]]:
    protected = {a.lower() for a in config.get("protected_attributes", [])}
    used_keys = {k.lower() for k in data.get("raw_fields", {})}
    hits = sorted(protected & used_keys)

    flags = [
        RuleFlag(
            code="PROTECTED_ATTRIBUTE_USED",
            severity=Severity.CRITICAL,
            message=(
                f"Protected attribute '{attribute}' was found in fields passed "
                "to decision logic, violating the RBI Fair Practices Code."
            ),
        )
        for attribute in hits
    ]

    status = "FAIL" if hits else "PASS"
    return {"status": status, "protected_attributes_detected": hits}, flags
