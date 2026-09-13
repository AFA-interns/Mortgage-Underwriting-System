"""LangGraph credit node - orchestrates the full Credit Analysis Agent
pipeline."""
from __future__ import annotations

from typing import Any

from app.agents.credit.crew import run_credit_reasoning
from app.credit.cibil import get_credit_band, get_credit_risk_tier
from app.credit.config import get_credit_config
from app.credit.employment import normalize_employment_type
from app.credit.foir import calculate_emi, calculate_foir, calculate_monthly_obligations, get_foir_threshold
from app.credit.ltv import calculate_ltv
from app.credit.red_flags import detect_red_flags
from app.credit.scoring import compute_confidence, compute_credit_risk_score, generate_preliminary_decision
from app.credit.stability import assess_income_stability
from app.graph.state import UnderwritingState
from app.models.decision import CreditAnalysisResult, Evidence
from app.services.credit_bureau import fetch_credit_report


def credit_node(state: UnderwritingState) -> dict[str, Any]:
    """LangGraph node implementing the Credit Analysis Agent.

    Reads state["borrower_profile"] (populated by the Document Ingestion
    Agent) and writes state["credit_analysis"] as a CreditAnalysisResult
    dict per the contract documented in README_credit.md.

    Every step except the final reasoning call is deterministic Python
    (app.credit.*) so the credit decision is auditable and reproducible -
    the LLM (app.agents.credit.crew) only explains the already-final
    preliminary_decision, it never sets or changes it.
    """
    errors: list[dict[str, Any]] = list(state.get("errors", []))
    borrower = state.get("borrower_profile") or {}
    application_id = state.get("application_id") or borrower.get("application_id") or "UNKNOWN"

    monthly_income = borrower.get("monthly_income", 0.0) or 0.0
    loan_amount = borrower.get("loan_amount", 0.0) or 0.0
    tenure_months = borrower.get("loan_tenure_months", 0) or 0
    property_value = borrower.get("property_value", 0.0) or 0.0
    declared_existing_emis = borrower.get("existing_debt", 0.0) or 0.0
    employment_type = normalize_employment_type(borrower.get("employment_type", ""))

    if monthly_income <= 0 or loan_amount <= 0 or tenure_months <= 0:
        errors.append(
            {
                "stage": "credit_analysis",
                "message": (
                    "borrower_profile missing/non-positive monthly_income, "
                    "loan_amount, or loan_tenure_months - cannot run credit analysis"
                ),
            }
        )
        result = CreditAnalysisResult(
            raw_data={"monthly_income": monthly_income, "property_value": property_value},
        )
        return {"credit_analysis": result.model_dump(), "errors": errors}

    # TODO: replace with a real credit bureau API call. state["credit_bureau_data"]
    # is an optional override so tests/integrations can supply real or
    # synthetic bureau data without touching the stub.
    bureau_data = state.get("credit_bureau_data") or fetch_credit_report(application_id)

    assumed_rate = get_credit_config()["foir"]["assumed_annual_interest_rate_percent"]
    proposed_emi = calculate_emi(loan_amount, assumed_rate, tenure_months)

    cibil_score = bureau_data.get("cibil_score")
    credit_band = get_credit_band(cibil_score)
    credit_risk_tier = get_credit_risk_tier(credit_band)

    foir_threshold = get_foir_threshold(employment_type)
    foir = calculate_foir(monthly_income, declared_existing_emis, proposed_emi, bureau_data)
    monthly_obligations = calculate_monthly_obligations(declared_existing_emis, proposed_emi, bureau_data)

    ltv = calculate_ltv(loan_amount, property_value)

    flags = detect_red_flags(employment_type, monthly_income, loan_amount, bureau_data)
    income_stability = assess_income_stability(employment_type, flags)

    confidence = compute_confidence(cibil_score, flags)
    risk_score = compute_credit_risk_score(credit_band, foir, foir_threshold, flags)
    preliminary_decision = generate_preliminary_decision(cibil_score, credit_band, foir, foir_threshold, flags)

    # CreditAnalysisResult.foir/ltv are bounded to [0, 1]/[0, 2] by the shared
    # model - an applicant whose obligations already exceed their entire
    # income (or LTV > 200%) is an obvious reject via
    # generate_preliminary_decision regardless, so clamping the *stored*
    # value here loses no decisioning information (the unclamped foir was
    # already used above).
    foir_for_model = min(foir, 1.0)
    ltv_for_model = min(ltv, 2.0) if ltv is not None else None

    result = CreditAnalysisResult(
        cibil_score=cibil_score,
        credit_risk_tier=credit_risk_tier,
        credit_band=credit_band,
        foir=foir_for_model,
        monthly_obligations=monthly_obligations,
        ltv=ltv_for_model,
        income_stability=income_stability,
        confidence=confidence,
        risk_score=risk_score,
        preliminary_decision=preliminary_decision,
        flags=flags,
        evidence=[
            Evidence(agent="credit", field="cibil_score", value=cibil_score, source="credit_bureau"),
            Evidence(agent="credit", field="foir", value=foir_for_model, source="app.credit.foir"),
            Evidence(agent="credit", field="ltv", value=ltv_for_model, source="app.credit.ltv"),
        ],
        raw_data={
            "monthly_income": monthly_income,
            "property_value": property_value,
            "employment_type": employment_type,
            "proposed_emi": proposed_emi,
            "declared_existing_emis": declared_existing_emis,
            "foir_threshold": foir_threshold,
            "assumed_annual_interest_rate_percent": assumed_rate,
        },
    )

    result.reasoning = run_credit_reasoning(borrower, result.model_dump())

    return {"credit_analysis": result.model_dump(), "errors": errors}
