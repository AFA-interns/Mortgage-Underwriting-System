"""Agent comparator — compares upstream agent assessments and identifies disagreements."""
from __future__ import annotations

from typing import Any

from app.models.decision import AgentComparison


def _extract_credit_summary(credit: dict[str, Any]) -> dict[str, Any]:
    credit = credit or {}
    return {
        "cibil_score": credit.get("cibil_score"),
        "credit_risk_tier": credit.get("credit_risk_tier", "unknown"),
        "foir": credit.get("foir"),
        "ltv": credit.get("ltv"),
        "income_stability": credit.get("income_stability", "unknown"),
        "confidence": credit.get("confidence", 0),
    }


def _extract_property_summary(property_data: dict[str, Any]) -> dict[str, Any]:
    property_data = property_data or {}
    return {
        "estimated_value": property_data.get("estimated_value", 0),
        "valuation_confidence": property_data.get("valuation_confidence", 0),
        "rera_status": property_data.get("rera_status", "unknown"),
    }


def _extract_compliance_summary(compliance: dict[str, Any]) -> dict[str, Any]:
    compliance = compliance or {}
    return {
        "kyc_cdd_status": compliance.get("kyc_cdd", {}).get("status", "unknown"),
        "pmla_status": compliance.get("pmla_source_of_funds", {}).get("status", "unknown"),
        "rbi_fair_practices_status": compliance.get(
            "rbi_fair_practices", {}
        ).get("status", "unknown"),
        "critical_flags_count": len(compliance.get("critical_flags", [])),
        "confidence": compliance.get("confidence", 0),
    }


def _extract_document_summary(doc_analysis: dict[str, Any]) -> dict[str, Any]:
    doc_analysis = doc_analysis or {}
    return {
        "verification_status": doc_analysis.get("verification_status", "unknown"),
        "missing_doc_count": len(doc_analysis.get("missing_documents", [])),
        "extraction_confidence": doc_analysis.get("extraction_confidence", 0),
    }


def compare_agents(case: dict[str, Any]) -> AgentComparison:
    """Compare assessments across all upstream agents and identify material disagreements."""
    credit = case.get("credit_analysis") or {}
    property_data = case.get("property_analysis") or {}
    compliance = case.get("compliance_analysis") or {}
    doc_analysis = case.get("document_analysis") or {}

    credit_summary = _extract_credit_summary(credit)
    property_summary = _extract_property_summary(property_data)
    compliance_summary = _extract_compliance_summary(compliance)
    doc_summary = _extract_document_summary(doc_analysis)

    # Identify areas of agreement and disagreement
    agreement_fields: list[str] = []
    disagreement_fields: list[str] = []

    # Check income consistency across sources
    doc_income = doc_analysis.get("income", {}).get("monthly_income")
    credit_income = credit.get("raw_data", {}).get("monthly_income")
    if doc_income and credit_income:
        if abs(float(doc_income) - float(credit_income)) / max(float(doc_income), 1) < 0.1:
            agreement_fields.append("monthly_income")
        else:
            disagreement_fields.append("monthly_income")

    # Check property value consistency
    prop_value = property_data.get("estimated_value", 0)
    bp_prop_value = case.get("borrower_profile", {}).get("property_value", 0)
    if prop_value and bp_prop_value:
        if abs(prop_value - bp_prop_value) / max(prop_value, 1) < 0.1:
            agreement_fields.append("property_value")
        else:
            disagreement_fields.append("property_value")

    # Check LTV consistency
    credit_ltv = credit.get("ltv")
    bp = case.get("borrower_profile", {})
    if credit_ltv and bp.get("property_value") and bp.get("loan_amount"):
        calculated_ltv = bp["loan_amount"] / bp["property_value"]
        if abs(credit_ltv - calculated_ltv) < 0.05:
            agreement_fields.append("ltv")
        else:
            disagreement_fields.append("ltv")

    # Material disagreement: income or property value disagreement
    material_disagreement = len(disagreement_fields) > 0 and any(
        f in disagreement_fields for f in ["monthly_income", "property_value"]
    )

    confidence_comparison = {
        "credit": credit.get("confidence", 0),
        "property": property_data.get("valuation_confidence", 0),
        "compliance": compliance.get("confidence", 0),
        "document": doc_analysis.get("extraction_confidence", 0),
    }

    details = {
        "credit_summary": credit_summary,
        "property_summary": property_summary,
        "compliance_summary": compliance_summary,
        "document_summary": doc_summary,
    }

    return AgentComparison(
        assessments_compared=["credit", "property", "compliance", "document"],
        confidence_comparison=confidence_comparison,
        agreement_fields=agreement_fields,
        disagreement_fields=disagreement_fields,
        material_disagreement=material_disagreement,
        details=details,
    )
