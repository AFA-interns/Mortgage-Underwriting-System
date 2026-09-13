"""Configuration loader for the Credit Analysis Agent.

Mirrors the pattern used by app.decision.risk_engine: read
backend/config/credit_config.yaml if present, otherwise fall back to
in-code defaults so the agent still runs (and is unit-testable) in a fresh
checkout before the config file is deployed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "credit_config.yaml"

_DEFAULTS: dict[str, Any] = {
    "cibil": {
        "bands": {"excellent": 750, "good": 700, "fair": 650, "poor": 550},
        "risk_tier_map": {
            "excellent": "low",
            "good": "low",
            "fair": "moderate",
            "poor": "high",
            "very_poor": "high",
            "new_to_credit": "moderate",
        },
    },
    "foir": {
        "thresholds": {"salaried": 0.55, "self_employed": 0.45, "business": 0.45},
        "credit_card_emi_equivalent_rate": 0.05,
        "assumed_annual_interest_rate_percent": 8.5,
    },
    "red_flags": {
        "loan_stacking_enquiry_threshold": 3,
        "income_to_loan_multiple": {"salaried": 6, "self_employed": 5, "business": 5},
    },
    "decision": {
        "cibil_hard_reject_threshold": 550,
        "foir_reject_overshoot": 0.15,
        "compensating_foir_headroom": 0.10,
    },
    "risk_score": {
        "weights": {"credit_band": 0.45, "foir": 0.35, "red_flags": 0.20},
        "red_flag_penalty": {"severe": 30.0, "mild": 12.0},
    },
    "confidence": {
        "base": 0.90,
        "no_credit_history_penalty": 0.30,
        "per_red_flag_penalty": 0.05,
        "floor": 0.30,
    },
}

_cached_config: dict[str, Any] | None = None


def get_credit_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load backend/config/credit_config.yaml, caching the result. Falls
    back to in-code defaults if the file is missing, so tests and a fresh
    checkout work without requiring the YAML file to exist."""
    global _cached_config
    if config_path is None and _cached_config is not None:
        return _cached_config

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    loaded = None
    if path.exists():
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)

    config = loaded if loaded else _DEFAULTS
    if config_path is None:
        _cached_config = config
    return config
