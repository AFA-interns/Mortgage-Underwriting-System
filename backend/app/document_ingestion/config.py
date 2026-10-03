"""Configuration loader for the Document Ingestion Agent.

Mirrors app.credit.config / app.compliance.config: read
backend/config/document_ingestion_config.yaml if present, otherwise fall
back to in-code defaults so the agent still runs (and is unit-testable) in
a fresh checkout before the config file is deployed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "document_ingestion_config.yaml"

_DEFAULTS: dict[str, Any] = {
    "salary_slip": {
        "recency_window_months": 3,
    },
}

_cached_config: dict[str, Any] | None = None


def get_document_ingestion_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load backend/config/document_ingestion_config.yaml, caching the
    result. Falls back to in-code defaults if the file is missing."""
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
