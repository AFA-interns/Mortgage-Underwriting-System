"""Composite scoring and the Credit Analysis Agent's own preliminary
decision.

This is the ONLY place that decision is made. The LLM reasoning node
(app.agents.credit.crew) only explains the result afterwards - it never
sets or overrides preliminary_decision.
"""
from __future__ import annotations

from app.credit.config import get_credit_config
from app.credit.red_flags import count_severe_red_flags
from app.models.decision import CreditDecisionType

CREDIT_BAND_SCORES = {
    "Excellent": 100.0,
    "Good": 82.0,
    "Fair": 62.0,
    "Poor": 35.0,
    "Very Poor": 10.0,
    "New-to-Credit": 50.0,  # unproven, treated as neutral rather than adverse
}


def compute_credit_risk_score(
    credit_band: str,
    foir: float,
    foir_threshold: float,
    red_flags: list[str],
) -> float:
    """Weighted composite, 0-100 (higher = lower risk). This is the Credit
    Analysis Agent's OWN internal score - distinct from (and one input
    into) the Decision Agent's separate 6-component
    app.decision.risk_engine.calculate_risk_score."""
    weights = get_credit_config()["risk_score"]["weights"]
    penalties = get_credit_config()["risk_score"]["red_flag_penalty"]

    credit_band_score = CREDIT_BAND_SCORES.get(credit_band, CREDIT_BAND_SCORES["New-to-Credit"])

    # FOIR headroom: 100 at FOIR=0, 50 exactly at the threshold, drops (or
    # rises) linearly from there. Clamped to [0, 100].
    if foir_threshold > 0:
        headroom_ratio = (foir_threshold - foir) / foir_threshold
        foir_score = max(0.0, min(100.0, 50.0 + headroom_ratio * 100.0))
    else:
        foir_score = 0.0

    severe = count_severe_red_flags(red_flags)
    mild = len(red_flags) - severe
    red_flag_score = max(0.0, 100.0 - severe * penalties["severe"] - mild * penalties["mild"])

    score = (
        credit_band_score * weights["credit_band"]
        + foir_score * weights["foir"]
        + red_flag_score * weights["red_flags"]
    )
    return round(max(0.0, min(100.0, score)), 2)


def compute_confidence(cibil_score: int | None, red_flags: list[str]) -> float:
    """How reliable THIS assessment is (evidence quality) - not the
    borrower's creditworthiness. Mirrors the meaning of `confidence` used
    elsewhere in this system (see app.decision.confidence)."""
    cfg = get_credit_config()["confidence"]
    score = cfg["base"]
    if cibil_score is None:
        score -= cfg["no_credit_history_penalty"]
    score -= len(red_flags) * cfg["per_red_flag_penalty"]
    return round(max(cfg["floor"], min(1.0, score)), 2)


def generate_preliminary_decision(
    cibil_score: int | None,
    credit_band: str,
    foir: float,
    foir_threshold: float,
    red_flags: list[str],
) -> CreditDecisionType:
    cfg = get_credit_config()["decision"]
    severe_flags = count_severe_red_flags(red_flags)
    total_flags = len(red_flags)
    foir_overshoot = foir - foir_threshold  # <= 0 means within limit
    low_cibil = cibil_score is not None and cibil_score < cfg["cibil_hard_reject_threshold"]

    # --- reject conditions (checked first - reject is the strictest outcome) ---
    if low_cibil:
        has_compensating_factor = (
            foir_overshoot < -cfg["compensating_foir_headroom"] and total_flags == 0
        )
        if not has_compensating_factor:
            return CreditDecisionType.REJECT

    if foir_overshoot > cfg["foir_reject_overshoot"]:
        return CreditDecisionType.REJECT

    if severe_flags >= 2:
        return CreditDecisionType.REJECT

    # --- conditional conditions ---
    if low_cibil:
        # Below the hard-reject threshold but saved from an automatic reject
        # by a compensating factor - that still merits manual review, never
        # a clean approve.
        return CreditDecisionType.CONDITIONAL

    if foir_overshoot > 0:  # over threshold, but not enough to hit the reject band above
        return CreditDecisionType.CONDITIONAL

    if total_flags >= 1:  # any single red flag (severe or mild)
        return CreditDecisionType.CONDITIONAL

    if credit_band == "New-to-Credit":
        return CreditDecisionType.CONDITIONAL

    return CreditDecisionType.APPROVE
