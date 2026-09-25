from app.agents.compliance.crew import (
    _build_compliance_summary,
    _template_reasoning,
    run_compliance_reasoning,
)

CLEAN_RESULTS = {
    "kyc_cdd": {"status": "PASS"},
    "identity_consistency": "PASS",
    "pmla_source_of_funds": {"status": "PASS"},
    "rbi_fair_practices": {"status": "PASS"},
    "nhb": {"status": "PASS"},
    "rera": {"status": "PASS"},
    "critical_flags": [],
}

FLAGGED_RESULTS = {
    **CLEAN_RESULTS,
    "kyc_cdd": {"status": "FAIL"},
    "critical_flags": ["KYC_INCOMPLETE: Required KYC document 'PAN' was not submitted."],
}


def test_summary_includes_all_six_categories():
    summary = _build_compliance_summary(CLEAN_RESULTS)
    for label in ["KYC/CDD", "Identity consistency", "PMLA", "RBI Fair Practices", "NHB", "RERA"]:
        assert label in summary


def test_template_reasoning_clean_case():
    text = _template_reasoning(CLEAN_RESULTS)
    assert "no critical issues" in text.lower()


def test_template_reasoning_flagged_case_mentions_flag():
    text = _template_reasoning(FLAGGED_RESULTS)
    assert "KYC_INCOMPLETE" in text


def test_run_compliance_reasoning_never_raises_and_returns_string():
    # No real LLM call — either crewai isn't installed (falls back to
    # template) or an LLM call fails in a test environment with no API
    # keys, which is caught and also falls back. Either way this must not
    # raise and must return non-empty text.
    result = run_compliance_reasoning(CLEAN_RESULTS)
    assert isinstance(result, str)
    assert len(result) > 0


def test_no_api_key_skips_llm_and_uses_template(monkeypatch):
    from unittest.mock import patch

    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    with patch("app.agents.compliance.crew.Agent", side_effect=AssertionError("LLM must not be used")):
        assert len(run_compliance_reasoning(CLEAN_RESULTS)) > 0
