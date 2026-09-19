"""CrewAI tools — narrow, controlled read-only tools for the Decision Crew."""
from __future__ import annotations

import json
from typing import Any

from crewai.tools import BaseTool

_GATE_KEYS = (
    "critical_compliance",
    "missing_inputs",
    "unresolved_critical_contradiction",
    "below_confidence_threshold",
)


class RiskCalculatorTool(BaseTool):
    """Read-only lookup that returns the pre-calculated risk assessment."""

    name: str = "risk_calculator"
    description: str = (
        "Retrieve the deterministic risk score and its components "
        "for the current application."
    )
    risk_json: str = ""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return self.risk_json or "{}"


class ConfidenceCalculatorTool(BaseTool):
    """Read-only lookup that returns the pre-calculated confidence assessment."""

    name: str = "confidence_calculator"
    description: str = (
        "Retrieve the deterministic confidence assessment "
        "for the current application."
    )
    confidence_json: str = ""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return self.confidence_json or "{}"


class PolicyValidatorTool(BaseTool):
    """Validate a proposed decision against known deterministic safety gates."""

    name: str = "policy_validator"
    description: str = (
        "Check whether a proposed decision (APPROVE/DENY/SUSPEND) "
        "complies with deterministic safety gates. Returns PASS or FAIL with reasons."
    )
    gates_json: str = "{}"

    def _run(self, decision: str = "", **kwargs: Any) -> str:
        if decision not in {"APPROVE", "DENY", "SUSPEND"}:
            return '{"status": "FAIL", "reason": "Invalid decision type"}'
        if decision == "APPROVE" and _gates_require_suspend(self._parsed_gates()):
            return (
                '{"status": "FAIL", "reason": '
                '"Cannot APPROVE when safety gates indicate SUSPEND"}'
            )
        return '{"status": "PASS", "reason": "Decision is consistent with policy gates"}'

    def _parsed_gates(self) -> dict[str, Any]:
        try:
            data = json.loads(self.gates_json)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


def _gates_require_suspend(gates: dict[str, Any]) -> bool:
    """Return True if any hard safety gate currently blocks APPROVE."""
    return any(gates.get(name) is True for name in _GATE_KEYS)