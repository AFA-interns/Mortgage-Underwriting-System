"""Bureau source tracking: simulated / declared / demo / real."""
import pytest

from app.graph.nodes import credit as credit_module
from app.graph.nodes.credit import credit_node
from app.services.credit_bureau import (
    SOURCE_BUREAU,
    SOURCE_DECLARED,
    SOURCE_SIMULATED,
    BureauNotConfigured,
    declared_score_report,
    fetch_credit_report,
    fetch_from_bureau,
    is_verified,
    map_bureau_response,
    resolve_bureau_data,
    validate_cibil_score,
)


@pytest.fixture(autouse=True)
def _mock_reasoning(monkeypatch):
    monkeypatch.setattr(credit_module, "run_credit_reasoning", lambda *_: "Mocked reasoning.")


def _state(**overrides):
    state = {
        "application_id": "LN-2026-0007",
        "borrower_profile": {
            "monthly_income": 100000, "employment_type": "salaried",
            "loan_amount": 3000000, "loan_tenure_months": 180,
            "property_value": 5000000, "existing_debt": 0,
        },
    }
    state.update(overrides)
    return state


def test_stub_is_tagged_simulated_and_deterministic():
    a, b = fetch_credit_report("LN-1"), fetch_credit_report("LN-1")
    assert a == b
    assert a["source"] == SOURCE_SIMULATED
    assert not is_verified(a)


def test_real_bureau_not_configured_falls_back_to_stub():
    with pytest.raises(BureauNotConfigured):
        fetch_from_bureau("LN-1")
    assert resolve_bureau_data("LN-1")["source"] == SOURCE_SIMULATED


def test_declared_score_report_and_validation():
    report = declared_score_report(742)
    assert report["cibil_score"] == 742 and report["source"] == SOURCE_DECLARED
    for bad in (299, 901, 0, -1):
        with pytest.raises(ValueError):
            validate_cibil_score(bad)


def test_map_bureau_response_handles_no_history_and_marks_verified():
    mapped = map_bureau_response({"cibil_score": -1, "max_dpd_last_12_months": 30})
    assert mapped["cibil_score"] is None  # new-to-credit
    assert mapped["max_dpd_last_12_months"] == 30
    assert mapped["source"] == SOURCE_BUREAU and is_verified(mapped)


def test_node_reports_bureau_source():
    ca = credit_node(_state(credit_bureau_data=declared_score_report(780)))["credit_analysis"]
    assert ca["cibil_score"] == 780
    assert ca["raw_data"]["bureau_source"] == SOURCE_DECLARED
    assert ca["evidence"][0]["source"] == "credit_bureau:applicant_declared"

    ca = credit_node(_state())["credit_analysis"]
    assert ca["raw_data"]["bureau_source"] == SOURCE_SIMULATED
