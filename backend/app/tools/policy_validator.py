"""CrewAI tools — narrow, controlled tools for the Decision Crew."""
from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool


class RiskCalculatorTool(BaseTool):
    """Read-only risk score lookup from pre-calculated assessment."""

    name: str = "risk_calculator"
    description: str = (
            "Retrieve the deterministic risk score and its components "
            "for the current application."
        )

    def _run(self, risk_json: str = "", **kwargs: Any) -> str:
        return risk_json


class ConfidenceCalculatorTool(BaseTool):
    """Read-only confidence score lookup from pre-calculated assessment."""

    name: str = "confidence_calculator"
    description: str = (
            "Retrieve the deterministic confidence assessment "
            "for the current application."
        )

    def _run(self, confidence_json: str = "", **kwargs: Any) -> str:
        return confidence_json


class PolicyValidatorTool(BaseTool):
    """Validate a proposed decision against known policy rules."""

    name: str = "policy_validator"
    description: str = (
        "Check whether a proposed decision (APPROVE/DENY/SUSPEND) "
        "complies with deterministic safety gates. Returns PASS or FAIL with reasons."
    )

    def _run(self, decision: str = "", gates_json: str = "", **kwargs: Any) -> str:
        if decision not in ("APPROVE", "DENY", "SUSPEND"):
            return '{"status": "FAIL", "reason": "Invalid decision type"}'
        if decision == "APPROVE" and "SUSPEND" in gates_json:
            return (
            '{"status": "FAIL", "reason": '
            '"Cannot APPROVE when safety gates indicate SUSPEND"}'
        )
        return '{"status": "PASS", "reason": "Decision is consistent with policy gates"}'
