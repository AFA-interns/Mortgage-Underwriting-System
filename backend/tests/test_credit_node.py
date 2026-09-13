"""Node-level tests for the Credit Analysis Agent (LLM reasoning
monkeypatched, mirroring how tests/test_e2e_pipeline.py exercises the
Decision Agent deterministically without CrewAI)."""
import pytest

import app.graph.nodes.credit as credit_node_module
from app.graph.nodes.credit import credit_node
from app.models.decision import CreditDecisionType


@pytest.fixture(autouse=True)
def mock_reasoning(monkeypatch):
    monkeypatch.setattr(
        credit_node_module, "run_credit_reasoning", lambda borrower, result: "Mocked reasoning."
    )


def _state(borrower_overrides=None, **overrides):
    borrower = {
        "application_id": "APP-TEST-01",
        "name": "Test Applicant",
        "employment_type": "salaried",
        "monthly_income": 90000,
        "loan_amount": 2000000,
        "loan_tenure_months": 180,
        "property_value": 3000000,
        "existing_debt": 5000,
    }
    borrower.update(borrower_overrides or {})
    state = {"application_id": "APP-TEST-01", "borrower_profile": borrower}
    state.update(overrides)
    return state


def test_salaried_approve_case():
    state = _state(
        credit_bureau_data={
            "cibil_score": 780,
            "settled_accounts": 0,
            "written_off_accounts": 0,
            "max_dpd_last_12_months": 0,
            "recent_enquiries_last_90_days": 0,
            "credit_card_outstanding_total": 0,
        }
    )
    result = credit_node(state)
    ca = result["credit_analysis"]

    assert ca["credit_band"] == "Excellent"
    assert ca["credit_risk_tier"] == "low"
    assert ca["preliminary_decision"] == CreditDecisionType.APPROVE.value
    assert ca["reasoning"] == "Mocked reasoning."
    assert not any(e.get("stage") == "credit_analysis" for e in result["errors"])


def test_self_employed_reject_bad_foir():
    state = _state(
        borrower_overrides={
            "employment_type": "self-employed",
            "monthly_income": 60000,
            "existing_debt": 20000,
        },
        credit_bureau_data={"cibil_score": 710},
    )
    result = credit_node(state)
    ca = result["credit_analysis"]

    assert ca["foir"] > 0.45
    assert ca["preliminary_decision"] == CreditDecisionType.REJECT.value


def test_na_credit_history_conditional():
    state = _state(credit_bureau_data={"cibil_score": None})
    result = credit_node(state)
    ca = result["credit_analysis"]

    assert ca["credit_band"] == "New-to-Credit"
    assert ca["preliminary_decision"] == CreditDecisionType.CONDITIONAL.value


def test_red_flag_triggered_reject():
    state = _state(
        credit_bureau_data={
            "cibil_score": 780,
            "settled_accounts": 1,
            "max_dpd_last_12_months": 95,
        }
    )
    result = credit_node(state)
    ca = result["credit_analysis"]

    assert len(ca["flags"]) >= 2
    assert ca["preliminary_decision"] == CreditDecisionType.REJECT.value


def test_missing_borrower_data_records_error_and_skips_reasoning():
    state = {"application_id": "APP-EMPTY", "borrower_profile": {}}
    result = credit_node(state)

    assert any(e.get("stage") == "credit_analysis" for e in result["errors"])
    assert result["credit_analysis"]["preliminary_decision"] is None
    assert result["credit_analysis"]["reasoning"] == ""


def test_ltv_computed_from_declared_property_value():
    state = _state(
        borrower_overrides={"property_value": 4000000},
        credit_bureau_data={"cibil_score": 780},
    )
    result = credit_node(state)
    ca = result["credit_analysis"]

    assert ca["ltv"] == pytest.approx(2000000 / 4000000)
