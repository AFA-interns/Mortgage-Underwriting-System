"""LLM service — configurable primary/fallback LLM provider."""
from __future__ import annotations

import os
from typing import Any

_PRIMARY_PROVIDER = os.getenv("PRIMARY_LLM_PROVIDER", "google")
_PRIMARY_MODEL = os.getenv("PRIMARY_LLM_MODEL", "gemini-2.0-flash")
_FALLBACK_PROVIDER = os.getenv("FALLBACK_LLM_PROVIDER", "groq")
_FALLBACK_MODEL = os.getenv("FALLBACK_LLM_MODEL", "llama-3.1-70b-versatile")


def get_llm_config() -> dict[str, Any]:
    """Return current LLM configuration (no secrets)."""
    return {
        "primary": {"provider": _PRIMARY_PROVIDER, "model": _PRIMARY_MODEL},
        "fallback": {"provider": _FALLBACK_PROVIDER, "model": _FALLBACK_MODEL},
    }


def llm_available() -> bool:
    """True when an API key exists for the primary provider. Callers skip the
    LLM entirely (and use their deterministic fallback) when it doesn't."""
    keys = {
        "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "groq": ("GROQ_API_KEY",),
        "openai": ("OPENAI_API_KEY",),
    }.get(_PRIMARY_PROVIDER.lower(), ())
    return any(os.getenv(k) for k in keys)
