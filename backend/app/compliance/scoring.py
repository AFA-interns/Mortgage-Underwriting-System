"""Deterministic confidence scoring for the Compliance Agent's own
assessment reliability — populates ComplianceAnalysisResult.confidence.

Same meaning as elsewhere in this system (app.decision.confidence,
app.credit.scoring): how reliable *this specific assessment* is, not a
judgment about the applicant.
"""
from __future__ import annotations

from app.models.decision import Severity

from .flags import RuleFlag


def compute_confidence(all_flags: list[RuleFlag], config: dict) -> float:
    cfg = config.get("confidence", {})
    base = cfg.get("base", 0.90)
    critical_penalty = cfg.get("critical_flag_penalty", 0.15)
    warning_penalty = cfg.get("warning_flag_penalty", 0.05)
    floor = cfg.get("floor", 0.30)

    critical_count = sum(1 for f in all_flags if f.severity == Severity.CRITICAL)
    warning_count = sum(
        1 for f in all_flags if f.severity in (Severity.MEDIUM, Severity.HIGH)
    )

    score = base - (critical_count * critical_penalty) - (warning_count * warning_penalty)
    return max(floor, min(1.0, round(score, 4)))
