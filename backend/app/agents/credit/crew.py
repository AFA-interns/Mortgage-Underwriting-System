"""CrewAI Credit reasoning - a single agent that explains the already-final
rule-based credit assessment.

It must NOT change preliminary_decision - the task prompt explicitly
forbids proposing a different one, matching how the Decision Agent's own
Report Writer role communicates a decision without changing it (see
app.agents.decision.crew).
"""
from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task


def _build_credit_summary(borrower: dict[str, Any], credit_result: dict[str, Any]) -> str:
    """Build a structured text summary for the reasoning agent. Pulled out
    as its own function (like decision's _build_case_summary) so it can be
    unit-tested without invoking a real LLM."""
    return "\n".join(
        [
            f"Applicant: {borrower.get('name', 'N/A')} ({borrower.get('employment_type', 'N/A')})",
            f"Monthly Income: INR {borrower.get('monthly_income', 0):,.0f}",
            f"Loan Amount: INR {borrower.get('loan_amount', 0):,.0f} over "
            f"{borrower.get('loan_tenure_months', 0)} months",
            "",
            f"CIBIL Score: {credit_result.get('cibil_score') or 'No credit history (NA)'}",
            f"Credit Band: {credit_result.get('credit_band', 'N/A')}",
            f"FOIR: {credit_result.get('foir')}",
            f"LTV: {credit_result.get('ltv')}",
            f"Income Stability: {credit_result.get('income_stability', 'N/A')}",
            f"Red Flags: {credit_result.get('flags') or 'None'}",
            f"Composite Risk Score: {credit_result.get('risk_score', 'N/A')}/100",
            "Preliminary Decision (already final - explain, do not override): "
            f"{credit_result.get('preliminary_decision', 'N/A')}",
        ]
    )


def run_credit_reasoning(borrower: dict[str, Any], credit_result: dict[str, Any]) -> str:
    """Execute a single CrewAI agent to explain the preliminary credit
    decision in plain language for the Decision Agent / an eventual
    applicant-facing summary. Any failure (LLM outage, parse error) degrades
    to a deterministic fallback string rather than raising - mirrors
    app.agents.decision.crew's failure handling."""
    summary = _build_credit_summary(borrower, credit_result)

    try:
        credit_analyst = Agent(
            role="Credit Risk Analyst",
            goal=(
                "Explain a mortgage applicant's already-finalized credit risk "
                "assessment clearly and concisely, for another automated agent "
                "and an eventual applicant-facing summary."
            ),
            backstory=(
                "You are a credit analyst at an Indian housing finance company. "
                "You do not make lending decisions yourself - you explain "
                "decisions already reached by deterministic underwriting rules, "
                "in plain, evidence-backed language."
            ),
            verbose=False,
            allow_delegation=False,
        )

        explain_task = Task(
            description=(
                "Explain the credit risk assessment below in 2-4 concise "
                "sentences. Do NOT propose a different decision than the one "
                "given - your only job is to explain the reasoning clearly.\n\n"
                f"{summary}"
            ),
            expected_output="A 2-4 sentence plain-language explanation.",
            agent=credit_analyst,
        )

        crew = Crew(
            agents=[credit_analyst],
            tasks=[explain_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        return str(result).strip()

    except Exception as e:
        return (
            f"[LLM reasoning unavailable: {e}] Preliminary decision "
            f"'{credit_result.get('preliminary_decision')}' was reached via rule-based "
            f"scoring - credit_band={credit_result.get('credit_band')}, "
            f"foir={credit_result.get('foir')}, flags={credit_result.get('flags')}, "
            f"risk_score={credit_result.get('risk_score')}."
        )
