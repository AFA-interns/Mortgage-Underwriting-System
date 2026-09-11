"""Tests for CrewAI Decision Crew."""
from app.agents.decision.crew import (
    _build_case_summary,
    _parse_crew_output,
)
from app.models.decision import CrewRole, DecisionType
from tests.conftest import get_good_case


def test_case_summary_contains_key_info():
    case = get_good_case()
    summary = _build_case_summary(
        case,
        risk={"score": 85, "level": "LOW", "key_positive_factors": [], "key_risk_factors": []},
        confidence={"score": 0.9, "below_threshold": False, "reasoning": "Good"},
        contradictions=[],
    )
    assert "Priya Sharma" in summary
    assert "CIBIL Score" in summary
    assert "Estimated Value" in summary


def test_parse_crew_output_valid_json():
    raw = '{"recommendation": "APPROVE", "confidence": 0.9, "reasoning": "Strong case"}'
    output = _parse_crew_output(raw, CrewRole.UNDERWRITER)
    assert output.recommendation == DecisionType.APPROVE
    assert output.confidence == 0.9


def test_parse_crew_output_invalid_json():
    output = _parse_crew_output("not json", CrewRole.RISK_ANALYST)
    assert output.recommendation is None
    assert "not json" in output.reasoning


def test_parse_crew_output_suspend():
    raw = '{"recommendation": "SUSPEND", "confidence": 0.5, "reasoning": "Need more info"}'
    output = _parse_crew_output(raw, CrewRole.REPORT_WRITER)
    assert output.recommendation == DecisionType.SUSPEND
