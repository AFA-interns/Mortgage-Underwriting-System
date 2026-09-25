"""Internal flag representation used only inside app.compliance while
running checks. Never exposed directly on ComplianceAnalysisResult — the
node collapses these into the plain list[str] `critical_flags` field and
the `rule_status` dict that the shared model actually defines
(app/models/decision.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.decision import Severity


@dataclass(frozen=True)
class RuleFlag:
    code: str
    severity: Severity
    message: str

    def as_critical_string(self) -> str:
        return f"{self.code}: {self.message}"
