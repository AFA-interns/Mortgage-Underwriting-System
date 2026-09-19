"""Live-LLM crew smoke test — skipped unless RUN_LIVE_TESTS=1."""
from __future__ import annotations

import os

import pytest

from app.agents.decision.crew import run_decision_crew
from app.services.llm import build_llm
from tests.conftest import get_good_case

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live LLM test. Set RUN_LIVE_TESTS=1 and configure API keys to run.",
)


def test_configured_llm_initializes():
    llm = build_llm()
    assert llm is not None


def test_crew_runs_with_live_llm():
    case = get_good_case()
    risk = {
        "score": 85.0,
        "level": "LOW",
        "key_positive_factors": ["Strong CIBIL score"],
        "key_risk_factors": [],
    }
    confidence = {"score": 0.9, "below_threshold": False, "reasoning": "Complete evidence"}

    result = run_decision_crew(case, risk, confidence, [])

    assert result.error is None
    assert result.underwriter.recommendation is not None
    assert result.risk_analyst.recommendation is not None
    assert result.report_writer.recommendation is not None
    assert result.execution_time_seconds > 0