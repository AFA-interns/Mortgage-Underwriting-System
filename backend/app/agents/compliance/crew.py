"""Compliance explanation: plain-language summary of the already-final rule
results. The rules engine decides; this only phrases the result.

Uses the local LLM (app.services.llm, Ollama) when it is running, and the
deterministic template otherwise, so the pipeline never blocks or needs an
API key.
"""
from __future__ import annotations

from typing import Any

from app.services.llm import explain

_SYSTEM = (
    "You are a compliance reviewer for Indian housing finance. Explain the "
    "compliance rule results below in 2-3 plain sentences for a human "
    "underwriter. State only what the results say. Never give or imply a "
    "loan verdict."
)


def _build_compliance_summary(rule_results: dict[str, Any]) -> str:
    """Pure function — the prompt's structured input. Unit-tested directly
    without invoking a real LLM, same pattern as
    app.agents.credit.crew._build_credit_summary / test_credit_crew.py.
    """
    lines = [
        f"KYC/CDD: {rule_results['kyc_cdd']['status']}",
        f"Identity consistency: {rule_results['identity_consistency']}",
        f"PMLA source of funds: {rule_results['pmla_source_of_funds']['status']}",
        f"RBI Fair Practices: {rule_results['rbi_fair_practices']['status']}",
        f"NHB priority sector: {rule_results['nhb']['status']}",
        f"RERA: {rule_results['rera']['status']}",
        f"Critical flags: {rule_results['critical_flags'] or 'None'}",
    ]
    return "\n".join(lines)


def _template_reasoning(rule_results: dict[str, Any]) -> str:
    """Deterministic fallback used when the local LLM is off, or its
    call fails/times out/mentions a verdict — the pipeline never blocks here."""
    if not rule_results["critical_flags"]:
        return "All compliance checks passed; no critical issues identified."
    flags_text = "; ".join(rule_results["critical_flags"])
    return (
        "Compliance review identified critical issue(s) requiring human "
        f"review: {flags_text}."
    )


def run_compliance_reasoning(rule_results: dict[str, Any]) -> str:
    """Explains the compliance results. Never raises and never changes them."""
    return explain(
        system=_SYSTEM,
        prompt=_build_compliance_summary(rule_results),
        fallback=_template_reasoning(rule_results),
    )
