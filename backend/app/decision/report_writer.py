"""Report writer — produces human-readable, evidence-backed underwriting report."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.decision import (
    ConfidenceAssessment,
    DecisionCrewOutput,
    DecisionResult,
    RiskAssessment,
    UnderwritingReport,
)


def generate_report(
    case: dict[str, Any],
    risk: RiskAssessment,
    confidence: ConfidenceAssessment,
    crew_result: DecisionCrewOutput | None,
    final_decision: DecisionResult,
) -> UnderwritingReport:
    """Generate a structured underwriting report without altering the final decision."""
    bp = case.get("borrower_profile", {})
    doc = case.get("document_analysis", {})
    credit = case.get("credit_analysis", {})
    prop = case.get("property_analysis", {})
    compliance = case.get("compliance_analysis", {})

    application_summary = {
        "application_id": final_decision.application_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "decision": final_decision.decision.value,
    }

    borrower_summary = {
        "name": bp.get("name", "N/A"),
        "age": bp.get("age"),
        "monthly_income": bp.get("monthly_income", 0),
        "employment_type": bp.get("employment_type", "N/A"),
        "employer": bp.get("employer", "N/A"),
        "loan_amount": bp.get("loan_amount", 0),
        "loan_tenure_months": bp.get("loan_tenure_months", 0),
        "property_value": bp.get("property_value", 0),
    }

    document_verification = {
        "status": doc.get("verification_status", "unknown"),
        "total_documents": len(doc.get("documents", [])),
        "missing_documents": doc.get("missing_documents", []),
        "extraction_confidence": doc.get("extraction_confidence", 0),
    }

    credit_assessment = {
        "cibil_score": credit.get("cibil_score"),
        "credit_risk_tier": credit.get("credit_risk_tier", "N/A"),
        "monthly_obligations": credit.get("monthly_obligations", 0),
        "income_stability": credit.get("income_stability", "N/A"),
        "flags": credit.get("flags", []),
    }

    foir_ltv = {
        "foir": credit.get("foir"),
        "ltv": credit.get("ltv"),
    }

    property_valuation = {
        "estimated_value": prop.get("estimated_value", 0),
        "market_range": (
            f"INR {prop.get('market_range_low', 0):,.0f} - "
            f"INR {prop.get('market_range_high', 0):,.0f}"
        ),
        "valuation_confidence": prop.get("valuation_confidence", 0),
        "price_per_sqft": prop.get("price_per_sqft", 0),
        "rera_status": prop.get("rera_status", "N/A"),
        "comparable_count": len(prop.get("comparables", [])),
    }

    compliance_section = {
        "kyc_cdd": compliance.get("kyc_cdd", {}).get("status", "N/A"),
        "pmla_source_of_funds": compliance.get("pmla_source_of_funds", {}).get("status", "N/A"),
        "rbi_fair_practices": compliance.get("rbi_fair_practices", {}).get("status", "N/A"),
        "critical_flags": compliance.get("critical_flags", []),
        "confidence": compliance.get("confidence", 0),
    }

    risk_score_section = {
        "score": risk.score,
        "level": risk.level.value,
        "components": [
            {
                "name": c.name,
                "weight": c.weight,
                "raw_score": c.raw_score,
                "weighted_score": c.weighted_score,
            }
            for c in risk.components
        ],
    }

    confidence_section = {
        "score": confidence.score,
        "below_threshold": confidence.below_threshold,
        "reasoning": confidence.reasoning,
        "factors": confidence.factors,
    }

    # Crew rationale
    crew_rationale = ""
    if crew_result:
        parts = []
        if crew_result.underwriter:
            parts.append(f"Underwriter: {crew_result.underwriter.reasoning}")
        if crew_result.risk_analyst:
            parts.append(f"Risk Analyst: {crew_result.risk_analyst.reasoning}")
        crew_rationale = " | ".join(parts)

    final_rationale = final_decision.rationale
    if crew_rationale:
        final_rationale = f"{final_rationale} | Crew: {crew_rationale}"

    human_review_status = "REQUIRED" if final_decision.human_review_required else "NOT_REQUIRED"

    return UnderwritingReport(
        application_id=final_decision.application_id,
        decision=final_decision.decision,
        application_summary=application_summary,
        borrower_summary=borrower_summary,
        document_verification=document_verification,
        credit_assessment=credit_assessment,
        foir_ltv=foir_ltv,
        property_valuation=property_valuation,
        compliance=compliance_section,
        risk_score_section=risk_score_section,
        confidence_section=confidence_section,
        positive_factors=final_decision.key_positive_factors,
        risk_factors=final_decision.key_risk_factors,
        final_recommendation=final_rationale,
        evidence=final_decision.evidence if hasattr(final_decision, "evidence") else [],
        human_review_status=human_review_status,
    )
