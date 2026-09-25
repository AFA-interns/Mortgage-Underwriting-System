"""CrewAI Compliance Reviewer — explains already-final rule results, never
overrides them. Mirrors app.agents.credit.crew's shape: single Agent,
LLM used for explanation only, deterministic fallback on any failure.

ASSUMPTION FLAGGED: app.services.llm currently only exposes
get_llm_config() (provider/model strings, no secrets) — it doesn't build a
LangChain/CrewAI LLM object itself. This module assumes CrewAI's
Agent(llm="<provider>/<model>") string form. If app.agents.credit.crew or
app.agents.decision.crew build the LLM object differently (e.g. an
explicit ChatGoogleGenerativeAI/ChatGroq instance, or a primary→fallback
retry helper), copy that exact pattern here instead — this was written
without sight of those two files.
"""
from __future__ import annotations

from typing import Any

from app.services.llm import get_llm_config

try:
    from crewai import Agent, Crew, Process, Task

    _CREWAI_AVAILABLE = True
except ImportError:
    _CREWAI_AVAILABLE = False


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
    """Deterministic fallback used when CrewAI isn't installed, or the LLM
    call fails/times out/mis-parses — the pipeline never blocks here."""
    if not rule_results["critical_flags"]:
        return "All compliance checks passed; no critical issues identified."
    flags_text = "; ".join(rule_results["critical_flags"])
    return (
        "Compliance review identified critical issue(s) requiring human "
        f"review: {flags_text}."
    )


def run_compliance_reasoning(rule_results: dict[str, Any]) -> str:
    """Runs the single-agent CrewAI Compliance Reviewer. Never asked to
    choose a verdict — rule_results are already final by the time this
    runs (see app.compliance.rules_engine). Falls back to a deterministic
    summary on any failure so the pipeline never blocks on this step,
    matching app.agents.decision.crew's failure handling.
    """
    summary = _build_compliance_summary(rule_results)

    if not _CREWAI_AVAILABLE:
        return _template_reasoning(rule_results)

    try:
        llm_cfg = get_llm_config()
        model_string = f"{llm_cfg['primary']['provider']}/{llm_cfg['primary']['model']}"

        reviewer = Agent(
            role="Compliance Reviewer",
            goal=(
                "Explain the compliance rule results in plain language for a "
                "human underwriter. Never suggest or imply an approve/deny/"
                "suspend decision — that is the Decision Agent's job."
            ),
            backstory=(
                "A regulatory compliance specialist for Indian housing "
                "finance who reviews KYC, PMLA, RBI Fair Practices, NHB, "
                "and RERA check results and writes a clear, plain-language "
                "summary for human reviewers."
            ),
            llm=model_string,
            verbose=False,
        )
        task = Task(
            description=(
                "Given the following already-finalized compliance rule "
                "results, write a 2-4 sentence plain-language explanation "
                "for a human underwriter. Do not suggest a final decision.\n\n"
                f"{summary}"
            ),
            expected_output="A 2-4 sentence plain-language compliance summary.",
            agent=reviewer,
        )
        crew = Crew(agents=[reviewer], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        text = str(result).strip()
        return text if text else _template_reasoning(rule_results)
    except Exception:
        # TODO (Phase 2): retry against FALLBACK_LLM_PROVIDER/MODEL before
        # falling back to the template, once the exact retry helper used by
        # app.agents.credit.crew / app.agents.decision.crew is confirmed.
        return _template_reasoning(rule_results)
