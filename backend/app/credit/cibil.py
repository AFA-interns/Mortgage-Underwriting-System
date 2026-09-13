"""CIBIL score band mapping and risk-tier classification.

CIBIL bands (per standard Indian bureau convention):
    750-900          Excellent
    700-749          Good
    650-699          Fair
    550-649          Poor
    300-549          Very Poor
    No history (NA)  New-to-Credit  (distinct from "Very Poor" - not an error)
"""
from __future__ import annotations

from app.credit.config import get_credit_config

NEW_TO_CREDIT_BAND = "New-to-Credit"


def get_credit_band(cibil_score: int | None) -> str:
    """Maps a CIBIL score to its band. `None` means no credit history yet -
    a distinct, valid outcome, not a missing-data error."""
    if cibil_score is None:
        return NEW_TO_CREDIT_BAND

    bands = get_credit_config()["cibil"]["bands"]
    # Bureau feeds occasionally return out-of-range sentinel values; clamp
    # rather than error so a bad upstream value degrades gracefully.
    score = max(300, min(900, cibil_score))

    if score >= bands["excellent"]:
        return "Excellent"
    if score >= bands["good"]:
        return "Good"
    if score >= bands["fair"]:
        return "Fair"
    if score >= bands["poor"]:
        return "Poor"
    return "Very Poor"


def get_credit_risk_tier(credit_band: str) -> str:
    """Maps our CIBIL band to the low/moderate/high risk-tier vocabulary the
    Decision Agent's risk engine expects in credit_analysis.credit_risk_tier
    (see app.decision.risk_engine._score_credit_history)."""
    tier_map = get_credit_config()["cibil"]["risk_tier_map"]
    key = credit_band.lower().replace("-", "_").replace(" ", "_")
    return tier_map.get(key, "moderate")
