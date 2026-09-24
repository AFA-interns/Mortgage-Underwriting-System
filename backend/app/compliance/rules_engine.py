"""Deterministic rules engine — runs all six compliance checks and shapes
their results into exactly the fields app.models.decision.ComplianceAnalysisResult
expects, plus the internal flag list scoring.py needs.
"""
from __future__ import annotations

from typing import Any

from .flags import RuleFlag
from .identity_consistency import check_identity_consistency
from .kyc_checks import check_kyc_cdd
from .nhb_priority_sector import check_nhb
from .pmla_aml import check_pmla_source_of_funds
from .rbi_fair_practices import check_rbi_fair_practices
from .rera_check import check_rera


def run_all_checks(data: dict[str, Any], config: dict) -> dict[str, Any]:
    kyc_cdd, kyc_flags = check_kyc_cdd(data, config)
    identity_status, identity_flags = check_identity_consistency(data, config)
    pmla, pmla_flags = check_pmla_source_of_funds(data, config)
    rbi, rbi_flags = check_rbi_fair_practices(data, config)
    nhb, nhb_flags = check_nhb(data, config)
    rera, rera_flags = check_rera(data, config)

    all_flags: list[RuleFlag] = (
        kyc_flags + identity_flags + pmla_flags + rbi_flags + nhb_flags + rera_flags
    )
    critical_flags = [f.as_critical_string() for f in all_flags if f.severity.value == "CRITICAL"]

    rule_status = {
        "kyc_cdd": kyc_cdd["status"],
        "identity_consistency": identity_status,
        "pmla_source_of_funds": pmla["status"],
        "rbi_fair_practices": rbi["status"],
        "nhb": nhb["status"],
        "rera": rera["status"],
    }

    return {
        "kyc_cdd": kyc_cdd,
        "identity_consistency": identity_status,
        "pmla_source_of_funds": pmla,
        "rbi_fair_practices": rbi,
        "nhb": nhb,
        "rera": rera,
        "rule_status": rule_status,
        "critical_flags": critical_flags,
        "all_flags": all_flags,  # internal only — used by scoring.py, not on the shared model
    }
