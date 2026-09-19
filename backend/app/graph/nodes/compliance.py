from __future__ import annotations

from typing import Any

from app.graph.state import UnderwritingState


def compliance_node(state: UnderwritingState) -> dict[str, Any]:
    """Placeholder compliance node — returns PASS status until real implementation.

    TODO: Teammate (Saurav) to implement full compliance checks:
    - KYC/CDD verification
    - PMLA source of funds check
    - RBI fair practices compliance
    - RERA registration verification
    - Critical flag detection
    """
    errors: list[dict[str, Any]] = list(state.get("errors", []))

    return {
        "compliance_analysis": {
            "kyc_cdd": {"status": "PASS"},
            "pmla_source_of_funds": {"status": "PASS"},
            "rbi_fair_practices": {"status": "PASS"},
            "critical_flags": [],
            "confidence": 0.90,
            "evidence": [],
            "rule_status": {},
        },
        "errors": errors,
    }
