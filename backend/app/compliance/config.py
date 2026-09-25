"""YAML loader + in-code fallback defaults for the Compliance Agent.
Mirrors app.credit.config.get_credit_config's pattern: if the file is
missing, tests and a fresh checkout still work.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "compliance_config.yaml"
)

_DEFAULTS: dict[str, Any] = {
    "required_kyc_documents": ["PAN", "AADHAAR", "ADDRESS_PROOF"],
    "fuzzy_match": {"name_match_threshold": 90},
    "pmla_aml": {
        "require_source_of_funds_declaration": True,
        "require_identity_verification_log": True,
    },
    "nhb_priority_sector": {"metro_ceiling": 3500000, "non_metro_ceiling": 2500000},
    "rera": {"required_for_under_construction": True},
    "protected_attributes": ["religion", "caste", "gender", "region"],
    "confidence": {
        "base": 0.90,
        "critical_flag_penalty": 0.15,
        "warning_flag_penalty": 0.05,
        "floor": 0.30,
    },
}


def get_compliance_config(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        return {**_DEFAULTS, **loaded}
    except FileNotFoundError:
        return dict(_DEFAULTS)
