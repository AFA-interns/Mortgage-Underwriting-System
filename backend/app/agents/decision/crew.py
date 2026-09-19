"""CrewAI Decision Crew — Underwriter, Risk Analyst, Report Writer."""
from __future__ import annotations

import json
import re
import time
from contextlib import suppress
from typing import Any

from crewai import LLM, Agent, Crew, Process, Task

from app.models.decision import (
    CrewMemberOutput,
    CrewRole,
    DecisionCrewOutput,
    DecisionType,
)
from app.services.llm import build_llm
from app.tools.policy_validator import (
    ConfidenceCalculatorTool,
    PolicyValidatorTool,
    RiskCalculatorTool,
)


def _build_case_summary(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list,
) -> str:
    """Build a structured text summary for the crew."""
    bp = case.get("borrower_profile", {})
    credit = case.get("credit_analysis", {})
    prop = case.get("property_analysis", {})
    compliance = case.get("compliance_analysis", {})

    parts = [
        f"Application ID: {case.get('application_id', 'N/A')}",
        f"Borrower: {bp.get('name', 'N/A')}, Age: {bp.get('age', 'N/A')}",
        f"Monthly Income: INR {bp.get('monthly_income', 0):,.0f}",
        f"Employment: {bp.get('employment_type', 'N/A')} at {bp.get('employer', 'N/A')}",
        f"Loan Amount: INR {bp.get('loan_amount', 0):,.0f}",
        f"Loan Tenure: {bp.get('loan_tenure_months', 0)} months",
        f"Property Value (declared): INR {bp.get('property_value', 0):,.0f}",
        f"Existing Debt: INR {bp.get('existing_debt', 0):,.0f}",
        "",
        "--- Credit Analysis ---",
        f"CIBIL Score: {credit.get('cibil_score', 'N/A')}",
        f"Credit Risk Tier: {credit.get('credit_risk_tier', 'N/A')}",
        f"FOIR: {credit.get('foir', 'N/A')}",
        f"LTV: {credit.get('ltv', 'N/A')}",
        f"Income Stability: {credit.get('income_stability', 'N/A')}",
        f"Credit Flags: {credit.get('flags', [])}",
        "",
        "--- Property Analysis ---",
        f"Estimated Value: INR {prop.get('estimated_value', 0):,.0f}",
        "Market Range: "
        f"INR {prop.get('market_range_low', 0):,.0f} - INR {prop.get('market_range_high', 0):,.0f}",
        f"Valuation Confidence: {prop.get('valuation_confidence', 0):.0%}",
        f"RERA Status: {prop.get('rera_status', 'N/A')}",
        f"Property Flags: {prop.get('flags', [])}",
        "",
        "--- Compliance ---",
        f"KYC/CDD: {compliance.get('kyc_cdd', {}).get('status', 'N/A')}",
        f"PMLA: {compliance.get('pmla_source_of_funds', {}).get('status', 'N/A')}",
        f"Critical Flags: {compliance.get('critical_flags', [])}",
        "",
        "--- Risk Assessment ---",
        f"Risk Score: {risk.get('score', 'N/A')}/100",
        f"Risk Level: {risk.get('level', 'N/A')}",
        f"Positive Factors: {risk.get('key_positive_factors', [])}",
        f"Risk Factors: {risk.get('key_risk_factors', [])}",
        "",
        "--- Confidence ---",
        f"Score: {confidence.get('score', 'N/A')}",
        f"Below Threshold: {confidence.get('below_threshold', 'N/A')}",
        f"Reasoning: {confidence.get('reasoning', 'N/A')}",
        "",
        f"--- Contradictions ({len(contradictions)}) ---",
    ]

    for c in contradictions:
        parts.append(
            f"  [{c.get('severity', 'MEDIUM')}] {c.get('field', 'N/A')}: "
            f"{c.get('description', 'N/A')} (Status: {c.get('resolution', 'UNRESOLVED')})"
        )

    return "\n".join(parts)


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Extract a JSON object from LLM output, tolerating markdown/prose wrapper."""
    if not isinstance(raw, str) or not raw.strip():
        return None

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*", "", text, flags=re.IGNORECASE)
        text = text.rstrip("`").strip()

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _parse_crew_output(raw: str, role: CrewRole) -> CrewMemberOutput:
    """Parse LLM crew output into structured CrewMemberOutput."""
    data = _extract_json(raw)
    if data is None:
        return CrewMemberOutput(
            role=role,
            reasoning=raw if isinstance(raw, str) else str(raw),
        )

    rec = None
    if "recommendation" in data and data["recommendation"]:
        with suppress(ValueError, AttributeError):
            rec = DecisionType(data["recommendation"].upper())

    return CrewMemberOutput(
        role=role,
        recommendation=rec,
        confidence=float(data.get("confidence", 0)),
        reasoning=data.get("reasoning", ""),
        key_factors=data.get("key_factors", []),
        risks_identified=data.get("risks_identified", []),
        missing_information=data.get("missing_information", []),
    )


def _build_gate_summary(
    case: dict[str, Any], confidence: dict, contradictions: list[dict]
) -> str:
    """Serialize the known deterministic safety gates for the policy validator tool."""
    compliance = case.get("compliance_analysis", {})
    gates = {
        "critical_compliance": bool(compliance.get("critical_flags")),
        "missing_inputs": False,
        "unresolved_critical_contradiction": any(
            c.get("resolution") == "UNRESOLVED"
            and c.get("severity") in ("HIGH", "CRITICAL")
            for c in contradictions
        ),
        "below_confidence_threshold": bool(confidence.get("below_threshold")),
    }
    return json.dumps(gates)


def run_decision_crew(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list[dict],
    llm: LLM | None = None,
) -> DecisionCrewOutput:
    """Execute the CrewAI Decision Crew with three role-based agents."""
    start_time = time.time()

    if llm is None:
        llm = build_llm()
    llm_kwargs: dict[str, Any] = {"llm": llm} if llm is not None else {}

    case_summary = _build_case_summary(case, risk, confidence, contradictions)
    risk_tool = RiskCalculatorTool(risk_json=json.dumps(risk))
    confidence_tool = ConfidenceCalculatorTool(confidence_json=json.dumps(confidence))
    policy_tool = PolicyValidatorTool(
        gates_json=_build_gate_summary(case, confidence, contradictions)
    )

    try:
        underwriter = Agent(
            role="Senior Mortgage Underwriter",
            goal=(
                "Review the structured mortgage application case and produce a recommendation "
                "(APPROVE, DENY, or SUSPEND) with reasoning and confidence."
            ),
            backstory=(
                "You are a seasoned mortgage underwriter with 20+ years of experience "
                "in Indian housing finance. "
                "You evaluate applications holistically, considering credit, property, "
                "compliance, and risk factors. "
                "You are conservative and evidence-driven."
            ),
            verbose=False,
            allow_delegation=False,
            tools=[risk_tool, confidence_tool],
            **llm_kwargs,
        )

        risk_analyst = Agent(
            role="Risk Analyst",
            goal=(
                "Independently challenge the underwriting assessment. Identify overlooked risks, "
                "inconsistencies, and weaknesses. Provide your own recommendation."
            ),
            backstory=(
                "You are a meticulous risk analyst who scrutinizes every detail. "
                "You focus on what could go wrong and test assumptions made by the underwriter. "
                "You flag any hidden risks or inconsistencies."
            ),
            verbose=False,
            allow_delegation=False,
            tools=[risk_tool, confidence_tool, policy_tool],
            **llm_kwargs,
        )

        report_writer = Agent(
            role="Report Writer",
            goal=(
                "Produce a clear, evidence-backed rationale for the decision. "
                "Do not change the decision — only communicate it clearly."
            ),
            backstory=(
                "You are a financial report writer who specializes in regulatory "
                "and audit-ready documentation. "
                "You produce concise, evidence-backed narratives suitable "
                "for human reviewers and auditors."
            ),
            verbose=False,
            allow_delegation=False,
            **llm_kwargs,
        )

        underwriter_task = Task(
            description=(
                f"Analyze the following mortgage application case and provide "
                f"your recommendation.\n\n"
                f"{case_summary}\n\n"
                "Respond in JSON format:\n"
                '{"recommendation": "APPROVE|DENY|SUSPEND", "confidence": 0.0-1.0, '
                '"reasoning": "...", "key_factors": [...], '
                '"risks_identified": [...], "missing_information": [...]}'
            ),
            expected_output=(
                "JSON with recommendation, confidence, reasoning, key_factors, "
                "risks_identified, missing_information"
            ),
            agent=underwriter,
        )

        risk_analyst_task = Task(
            description=(
                "Independently assess the risk of this mortgage application.\n\n"
                f"{case_summary}\n\n"
                "Provide your independent assessment and identify any risks "
                "the underwriter may have missed.\n"
                "Respond in JSON format:\n"
                '{"recommendation": "APPROVE|DENY|SUSPEND", "confidence": 0.0-1.0, '
                '"reasoning": "...", "key_factors": [...], '
                '"risks_identified": [...], "missing_information": [...]}'
            ),
            expected_output=(
                "JSON with recommendation, confidence, reasoning, key_factors, "
                "risks_identified, missing_information"
            ),
            agent=risk_analyst,
            context=[underwriter_task],
        )

        report_writer_task = Task(
            description=(
                "Based on the underwriter's and risk analyst's assessments, produce a clear "
                "rationale for the final decision. Include positive factors, risk factors, "
                "and any missing information.\n\n"
                f"Deterministic risk score: {risk.get('score', 'N/A')}/100.\n\n"
                "Respond in JSON format:\n"
                '{"recommendation": "APPROVE|DENY|SUSPEND", "confidence": 0.0-1.0, '
                '"reasoning": "...", "key_factors": [...], '
                '"risks_identified": [...], "missing_information": [...]}'
            ),
            expected_output=(
                "JSON with recommendation, confidence, reasoning, key_factors, "
                "risks_identified, missing_information"
            ),
            agent=report_writer,
            context=[underwriter_task, risk_analyst_task],
        )

        crew = Crew(
            agents=[underwriter, risk_analyst, report_writer],
            tasks=[underwriter_task, risk_analyst_task, report_writer_task],
            process=Process.sequential,
            verbose=False,
        )

        results = crew.kickoff()

        # Parse individual outputs
        task_results = results.tasks_output if hasattr(results, "tasks_output") else []

        uw_output = _parse_crew_output(
            str(task_results[0]) if len(task_results) > 0 else "",
            CrewRole.UNDERWRITER,
        )
        ra_output = _parse_crew_output(
            str(task_results[1]) if len(task_results) > 1 else "",
            CrewRole.RISK_ANALYST,
        )
        rw_output = _parse_crew_output(
            str(task_results[2]) if len(task_results) > 2 else "",
            CrewRole.REPORT_WRITER,
        )

        elapsed = time.time() - start_time

        return DecisionCrewOutput(
            underwriter=uw_output,
            risk_analyst=ra_output,
            report_writer=rw_output,
            execution_time_seconds=round(elapsed, 2),
        )

    except Exception as e:
        elapsed = time.time() - start_time
        return DecisionCrewOutput(
            execution_time_seconds=round(elapsed, 2),
            error=f"Crew execution failed: {e}",
        )
