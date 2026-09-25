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


def test_run_compliance_reasoning_uses_template_when_llm_is_off():
    result = run_compliance_reasoning(CLEAN_RESULTS)
    assert result == _template_reasoning(CLEAN_RESULTS)


def test_local_llm_text_is_used_when_available(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with patch("app.services.llm.llm_available", return_value=True),          patch("app.services.llm.httpx.post") as post:
        post.return_value.json.return_value = {"response": "KYC failed because the Aadhaar was not submitted."}
        post.return_value.raise_for_status = lambda: None
        text = run_compliance_reasoning(FLAGGED_RESULTS)
    assert text == "KYC failed because the Aadhaar was not submitted."


def test_llm_text_that_states_a_verdict_is_rejected(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with patch("app.services.llm.llm_available", return_value=True),          patch("app.services.llm.httpx.post") as post:
        post.return_value.json.return_value = {"response": "The application is eligible and should be approved."}
        post.return_value.raise_for_status = lambda: None
        text = run_compliance_reasoning(FLAGGED_RESULTS)
    assert text == _template_reasoning(FLAGGED_RESULTS)


def test_llm_failure_falls_back_to_template(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with patch("app.services.llm.llm_available", return_value=True),          patch("app.services.llm.httpx.post", side_effect=TimeoutError("slow")):
        assert run_compliance_reasoning(FLAGGED_RESULTS) == _template_reasoning(FLAGGED_RESULTS)
