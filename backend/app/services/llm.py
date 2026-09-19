"""LLM service — configurable primary/fallback LLM provider."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from crewai import LLM
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

_PRIMARY_PROVIDER = os.getenv("PRIMARY_LLM_PROVIDER", "google")
_PRIMARY_MODEL = os.getenv("PRIMARY_LLM_MODEL", "gemini-3.6-flash")
_FALLBACK_PROVIDER = os.getenv("FALLBACK_LLM_PROVIDER", "groq")
_FALLBACK_MODEL = os.getenv("FALLBACK_LLM_MODEL", "llama-3.1-70b-versatile")
_OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o")
_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

_PROVIDER_KEY_ENVS: dict[str, tuple[str, ...]] = {
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
}


def get_llm_config() -> dict[str, Any]:
    """Return current LLM configuration (no secrets)."""
    return {
        "primary": {"provider": _PRIMARY_PROVIDER, "model": _PRIMARY_MODEL},
        "fallback": {"provider": _FALLBACK_PROVIDER, "model": _FALLBACK_MODEL},
    }


def _provider_api_key(provider: str) -> str | None:
    """Best-effort API key lookup for a provider."""
    for var in _PROVIDER_KEY_ENVS.get(provider.lower(), ()):
        value = os.getenv(var)
        if value:
            return value
    return None


def _try_build_llm(
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> LLM | None:
    """Attempt to build a CrewAI LLM; return None if the provider is unavailable.

    Construction can fail when the provider's SDK/extra is not installed
    (e.g. ``crewai[google-genai]`` or ``crewai[litellm]``) or the model name
    is unsupported. Those failures are expected and swallowed.
    """
    try:
        return LLM(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=_provider_api_key(provider),
        )
    except Exception as exc:  # provider extra/SDK missing or model unsupported
        logger.debug("Could not build LLM provider=%s model=%s: %s", provider, model, exc)
        return None


def build_llm(
    temperature: float = _TEMPERATURE,
    max_tokens: int = _MAX_TOKENS,
) -> LLM | None:
    """Build the best available CrewAI LLM (primary -> fallback -> OpenAI).

    Returns ``None`` when no provider can be initialized, in which case
    CrewAI falls back to its own default (OpenAI ``gpt-4``).
    """
    candidates = [
        (_PRIMARY_PROVIDER, _PRIMARY_MODEL),
        (_FALLBACK_PROVIDER, _FALLBACK_MODEL),
        ("openai", _OPENAI_FALLBACK_MODEL),
    ]

    seen: set[tuple[str, str]] = set()
    for provider, model in candidates:
        key = (provider.lower(), model.lower())
        if key in seen or not model:
            continue
        seen.add(key)
        llm = _try_build_llm(provider, model, temperature, max_tokens)
        if llm is not None:
            logger.info("Selected LLM provider=%s model=%s", provider, model)
            return llm
        logger.warning(
            "LLM provider=%s model=%s unavailable; trying next candidate", provider, model
        )

    logger.warning("No configured LLM available; using CrewAI default (OpenAI).")
    return None