"""Deterministic Decision Crew — Underwriter, Risk Analyst, Report Writer.

No LLM required. Generates structured outputs that mirror what the
CrewAI agents would produce, based purely on deterministic rule-based
analysis of the case data.
"""
from __future__ import annotations

import time
from typing import Any

from app.models.decision import (
    CrewMemberOutput,
    CrewRole,
    DecisionCrewOutput,
    DecisionType,
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


def _deterministic_recommendation(
    risk_score: float,
    confidence: float,
    flags: list[str],
    compliance_critical: bool,
) -> tuple[DecisionType, float]:
    """Determine recommendation based on deterministic rules matching finalizer logic."""
    if compliance_critical:
        return DecisionType.SUSPEND, 0.95

    if risk_score >= 80 and confidence >= 0.85:
        return DecisionType.APPROVE, 0.9
    elif risk_score <= 40 and confidence >= 0.85:
        return DecisionType.DENY, 0.85
    else:
        return DecisionType.SUSPEND, 0.7


def _create_underwriter_output(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list,
) -> CrewMemberOutput:
    """Create deterministic underwriter output."""
    risk_score = risk.get("score", 0)
    conf = confidence.get("score", 0)
    flags = case.get("credit_analysis", {}).get("flags", [])
    critical_compliance = len(case.get("compliance_analysis", {}).get("critical_flags", [])) > 0

    rec, conf_level = _deterministic_recommendation(risk_score, conf, flags, critical_compliance)

    reasoning_parts = []
    if critical_compliance:
        reasoning_parts.append("Critical compliance flag triggers mandatory suspend.")
    elif risk_score >= 80:
        reasoning_parts.append(f"Strong risk score ({risk_score:.1f}/100) supports approval.")
    elif risk_score <= 40:
        reasoning_parts.append(f"Weak risk score ({risk_score:.1f}/100) warrants denial.")
    else:
        reasoning_parts.append(f"Risk score ({risk_score:.1f}/100) falls in review zone.")

    if flags:
        reasoning_parts.append(f"Credit flags present: {', '.join(flags)}.")

    return CrewMemberOutput(
        role=CrewRole.UNDERWRITER,
        recommendation=rec,
        confidence=conf_level,
        reasoning=" ".join(reasoning_parts),
        key_factors=[
            f"Risk score: {risk_score:.1f}/100",
            f"Confidence: {conf:.2f}",
            f"Credit tier: {case.get('credit_analysis', {}).get('credit_risk_tier', 'N/A')}",
        ],
        risks_identified=[f"Credit flag: {f}" for f in flags] + (
            ["Critical compliance flag"] if critical_compliance else []
        ),
        missing_information=[],
    )


def _create_risk_analyst_output(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list,
) -> CrewMemberOutput:
    """Create deterministic risk analyst output - more conservative."""
    risk_score = risk.get("score", 0)
    conf = confidence.get("score", 0)
    flags = case.get("credit_analysis", {}).get("flags", [])
    critical_compliance = len(case.get("compliance_analysis", {}).get("critical_flags", [])) > 0
    unresolved_critical = any(
        c.get("severity") == "CRITICAL" and c.get("resolution") == "UNRESOLVED"
        for c in contradictions
    )

    # Risk analyst is more conservative - more likely to SUSPEND
    if critical_compliance or unresolved_critical or risk_score < 50 or conf < 0.8:
        rec = DecisionType.SUSPEND
        conf_level = 0.9
    elif risk_score >= 85 and conf >= 0.9:
        rec = DecisionType.APPROVE
        conf_level = 0.85
    elif risk_score <= 35 and conf >= 0.9:
        rec = DecisionType.DENY
        conf_level = 0.8
    else:
        rec = DecisionType.SUSPEND
        conf_level = 0.75

    reasoning_parts = ["Independent risk assessment:"]
    if unresolved_critical:
        reasoning_parts.append("Unresolved critical contradiction requires suspension.")
    if critical_compliance:
        reasoning_parts.append("Critical compliance issue blocks approval.")
    if risk_score < 50:
        reasoning_parts.append(f"Risk score ({risk_score:.1f}) below comfort threshold.")
    if conf < 0.8:
        reasoning_parts.append(f"Confidence ({conf:.2f}) insufficient for decisive action.")
    if flags:
        reasoning_parts.append(f"Credit flags ({len(flags)}) elevate risk profile.")

    key_factors = [
        f"Risk score: {risk_score:.1f}/100",
        f"Confidence: {conf:.2f}",
    ]
    if flags:
        key_factors.append(f"Credit flags: {len(flags)}")
    if unresolved_critical:
        key_factors.append("Unresolved critical contradiction")

    return CrewMemberOutput(
        role=CrewRole.RISK_ANALYST,
        recommendation=rec,
        confidence=conf_level,
        reasoning=" ".join(reasoning_parts),
        key_factors=key_factors,
        risks_identified=[f"Credit flag: {f}" for f in flags] + (
            ["Unresolved critical contradiction"] if unresolved_critical else []
        ) + (["Critical compliance flag"] if critical_compliance else []),
        missing_information=[],
    )


def _create_report_writer_output(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list,
) -> CrewMemberOutput:
    """Create deterministic report writer output - communicates decision rationale."""
    risk_score = risk.get("score", 0)
    conf = confidence.get("score", 0)
    flags = case.get("credit_analysis", {}).get("flags", [])
    critical_compliance = len(case.get("compliance_analysis", {}).get("critical_flags", [])) > 0

    # Report writer aligns with the final decision logic
    if critical_compliance:
        rec = DecisionType.SUSPEND
        conf_level = 0.95
    elif risk_score >= 80 and conf >= 0.85:
        rec = DecisionType.APPROVE
        conf_level = 0.9
    elif risk_score <= 40 and conf >= 0.85:
        rec = DecisionType.DENY
        conf_level = 0.85
    else:
        rec = DecisionType.SUSPEND
        conf_level = 0.8

    reasoning_parts = ["Report rationale:"]
    if critical_compliance:
        reasoning_parts.append("Application suspended due to critical compliance finding.")
    elif rec == DecisionType.APPROVE:
        reasoning_parts.append(
            f"Application approved: risk score {risk_score:.1f} exceeds threshold, "
            f"confidence {conf:.2f} adequate."
        )
    elif rec == DecisionType.DENY:
        reasoning_parts.append(
            f"Application denied: risk score {risk_score:.1f} below threshold, "
            f"confidence {conf:.2f} supports decision."
        )
    else:
        reasoning_parts.append(
            f"Application suspended for manual review: risk score {risk_score:.1f} "
            f"in review zone, confidence {conf:.2f}."
        )

    if flags:
        reasoning_parts.append(f"Credit flags noted: {', '.join(flags)}.")

    return CrewMemberOutput(
        role=CrewRole.REPORT_WRITER,
        recommendation=rec,
        confidence=conf_level,
        reasoning=" ".join(reasoning_parts),
        key_factors=[
            f"Risk score: {risk_score:.1f}/100",
            f"Confidence: {conf:.2f}",
            f"Decision: {rec.value}",
        ],
        risks_identified=[f"Credit flag: {f}" for f in flags] + (
            ["Critical compliance flag"] if critical_compliance else []
        ),
        missing_information=[],
    )


def run_decision_crew(
    case: dict[str, Any],
    risk: dict,
    confidence: dict,
    contradictions: list[dict],
) -> DecisionCrewOutput:
    """Execute deterministic decision crew - no LLM calls."""
    start_time = time.time()

    # Build deterministic outputs for each role
    underwriter = _create_underwriter_output(case, risk, confidence, contradictions)
    risk_analyst = _create_risk_analyst_output(case, risk, confidence, contradictions)
    report_writer = _create_report_writer_output(case, risk, confidence, contradictions)

    elapsed = time.time() - start_time

    return DecisionCrewOutput(
        underwriter=underwriter,
        risk_analyst=risk_analyst,
        report_writer=report_writer,
        execution_time_seconds=round(elapsed, 2),
    )