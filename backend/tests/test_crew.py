"""Tests for CrewAI Decision Crew."""
from app.agents.decision.crew import (
    _build_case_summary,
    _extract_json,
    _parse_crew_output,
)
from app.models.decision import CrewRole, DecisionType
from app.tools.policy_validator import (
    ConfidenceCalculatorTool,
    PolicyValidatorTool,
    RiskCalculatorTool,
)
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


def test_parse_crew_output_markdown_fenced():
    raw = '```json\n{"recommendation": "APPROVE", "confidence": 0.88, "reasoning": "Good"}\n```'
    output = _parse_crew_output(raw, CrewRole.UNDERWRITER)
    assert output.recommendation == DecisionType.APPROVE
    assert output.confidence == 0.88


def test_parse_crew_output_prose_with_embedded_json():
    raw = (
        "Based on the assessment, my recommendation is: "
        '{"recommendation": "DENY", "confidence": 0.7, '
        '"reasoning": "High FOIR and unstable income"}.'
    )
    output = _parse_crew_output(raw, CrewRole.RISK_ANALYST)
    assert output.recommendation == DecisionType.DENY
    assert output.confidence == 0.7


def test_extract_json_handles_empty_and_invalid():
    assert _extract_json("") is None
    assert _extract_json("not json at all") is None


def test_risk_tool_returns_stored_data():
    tool = RiskCalculatorTool(risk_json='{"score": 85}')
    assert tool._run() == '{"score": 85}'


def test_confidence_tool_returns_stored_data():
    tool = ConfidenceCalculatorTool(confidence_json='{"score": 0.9}')
    assert tool._run(args_ignored=True) == '{"score": 0.9}'


def test_policy_tool_rejects_approve_when_gates_fail():
    tool = PolicyValidatorTool(gates_json='{"critical_compliance": true}')
    assert "FAIL" in tool._run(decision="APPROVE")


def test_policy_tool_passes_when_gates_clear():
    tool = PolicyValidatorTool(gates_json='{"critical_compliance": false}')
    assert "PASS" in tool._run(decision="APPROVE")


def test_policy_tool_rejects_invalid_decision():
    tool = PolicyValidatorTool(gates_json="{}")
    assert "FAIL" in tool._run(decision="MAYBE")
