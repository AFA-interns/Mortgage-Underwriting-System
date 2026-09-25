"""Local LLM (Ollama) used ONLY to phrase explanations.

Every decision in this system is rule-based. Agents call `explain()` to turn
their final, already-computed results into plain language. It never raises
and never blocks the pipeline: if Ollama is off, slow, unreachable, or the
model's answer mentions a verdict, the caller's deterministic `fallback`
text is returned instead.

Configuration (backend/.env):
    LLM_PROVIDER=ollama        # or "none" to always use the fixed templates
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=llama3.2
    OLLAMA_TIMEOUT_SECONDS=45
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# An explanation must not smuggle in a verdict: that is the Decision Agent's job.
_VERDICT_WORDS = re.compile(
    r"\b(approv\w*|den(y|ied|ies|ial)|reject\w*|suspend\w*|declin\w*|recommend\w*|eligible)\b", re.I
)

_reachable: tuple[bool, float] = (False, 0.0)  # (result, checked_at)


def get_llm_config() -> dict[str, Any]:
    """Current LLM configuration (no secrets)."""
    return {
        "provider": os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
        "url": os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "timeout": float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45")),
    }


def llm_available() -> bool:
    """True when the provider is ollama and its server answers (cached 30s)."""
    global _reachable
    cfg = get_llm_config()
    if cfg["provider"] != "ollama":
        return False
    ok, checked = _reachable
    if time.time() - checked < 30:
        return ok
    try:
        ok = httpx.get(f"{cfg['url']}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        ok = False
    _reachable = (ok, time.time())
    return ok


def explain(system: str, prompt: str, fallback: str, max_tokens: int = 160) -> str:
    """Local-LLM explanation, or `fallback` on any problem."""
    if not llm_available():
        return fallback
    cfg = get_llm_config()
    try:
        res = httpx.post(
            f"{cfg['url']}/api/generate",
            json={
                "model": cfg["model"],
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": max_tokens},
            },
            timeout=cfg["timeout"],
        )
        res.raise_for_status()
        text = str(res.json().get("response", "")).strip()
    except Exception as exc:
        logger.warning("Local LLM explanation failed, using template: %s", exc)
        return fallback

    if not text:
        return fallback
    if _VERDICT_WORDS.search(text):
        logger.warning("Local LLM explanation mentioned a verdict; using template instead.")
        return fallback
    return text
