"""RERA registration check for under-construction properties.

Populates ComplianceAnalysisResult.rera. Gates trust in the Property
Valuation Agent's output: for under-construction properties, that output
is only reliable once RERA registration is confirmed.

Reads property_analysis.rera_status (per README_decision.md's Property
Analysis input contract: "REGISTERED" / other) rather than a boolean, to
match what the Property Valuation Agent actually emits.
"""
from __future__ import annotations

from typing import Any

from app.models.decision import Severity

from .flags import RuleFlag


def check_rera(data: dict[str, Any], config: dict) -> tuple[dict, list[RuleFlag]]:
    if not config.get("rera", {}).get("required_for_under_construction", True):
        return {"status": "PASS", "registered": None}, []

    prop = data.get("property", {})
    under_construction = bool(prop.get("under_construction", False))
    rera_status = prop.get("rera_status", "unknown")
    registered = rera_status == "REGISTERED"

    if not under_construction:
        return {"status": "NOT_APPLICABLE", "registered": None}, []

    if registered:
        return {"status": "PASS", "registered": True}, []

    flags = [
        RuleFlag(
            code="RERA_NOT_REGISTERED",
            severity=Severity.CRITICAL,
            message=(
                "Property is under construction but the builder/project is not "
                "RERA-registered; Property Valuation Agent output cannot be "
                "treated as reliable."
            ),
        )
    ]
    return {"status": "FAIL", "registered": False}, flags
