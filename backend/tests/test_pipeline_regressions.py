"""Regression tests for bugs found while running the full pipeline."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.graph.nodes.compliance import compliance_node
from app.graph.workflow import build_underwriting_graph
from app.main import app
from app.tools.external_api import fetch_api_valuation


def _doc_out(with_aadhaar=True, pan_name="Aarav Sharma"):
    out = {
        "pan_card": {"pan_number": "ABCPS1234F", "full_name": pan_name, "is_valid_format": True},
        "salary_slips": [{"employee_name": "Aarav Sharma"}],
        "bank_statement": {"account_holder_name": "Aarav Sharma"},
        "borrower_kyc": {"primary_name": "Aarav Sharma", "residential_address": "Flat 1, Coimbatore"},
        "property_profile": {"city": "Coimbatore"},
    }
    if with_aadhaar:
        out["aadhaar_card"] = {
            "full_name": "Aarav Sharma", "address": "Flat 1, Coimbatore", "is_valid_format": True,
        }
    return out


def _state(doc_out):
    return {
        "borrower_profile": {"name": "Aarav Sharma", "loan_amount": 5_000_000},
        "doc_ingestion_output": doc_out,
        "document_analysis": {"kyc": {"status": "complete"}},
    }


def test_compliance_node_returns_only_its_own_key():
    # Returning the whole state caused INVALID_CONCURRENT_GRAPH_UPDATE in the graph.
    assert set(compliance_node(_state(_doc_out()))) == {"compliance_analysis"}


def test_compliance_reads_real_doc_ingestion_output_clean():
    c = compliance_node(_state(_doc_out()))["compliance_analysis"]
    assert c["critical_flags"] == []
    assert c["rule_status"]["kyc_cdd"] == "PASS"
    assert c["rule_status"]["pmla_source_of_funds"] == "PASS"
    assert c["nhb"]["priority_sector_eligible"] is False  # 50L > non-metro ceiling, non-critical


def test_compliance_missing_aadhaar_is_critical():
    c = compliance_node(_state(_doc_out(with_aadhaar=False)))["compliance_analysis"]
    assert any("AADHAAR" in f for f in c["critical_flags"])


def test_compliance_name_mismatch_is_warning_only():
    c = compliance_node(_state(_doc_out(pan_name="Zed Unrelated")))["compliance_analysis"]
    assert c["rule_status"]["identity_consistency"] == "WARNING"
    assert c["critical_flags"] == []


def test_avnester_failure_degrades_to_empty_valuation():
    with patch("app.tools.external_api.search_properties", side_effect=ConnectionError("reset")):
        out = fetch_api_valuation("Saravanampatti", "Coimbatore", "Apartment", 2, 1450)
    assert out["estimated_market_value_inr"] == 0
    assert out["comparables"] == []


def test_property_search_endpoint_is_not_broken():
    with patch("app.main.search_properties", return_value={"total": 0, "listings": []}):
        r = TestClient(app).post("/property/search", json={"city": "Coimbatore"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_full_graph_runs_parallel_agents_without_state_conflict():
    graph = build_underwriting_graph().compile()
    with patch("app.tools.external_api.search_properties", return_value={"listings": []}):
        result = graph.invoke({
            "application_id": "REG-1",
            "raw_document_paths": [],
            "borrower_profile": {
                "name": "Aarav Sharma", "monthly_income": 150000, "employment_type": "Salaried",
                "loan_amount": 5_000_000, "loan_tenure_months": 240,
                "property_value": 7_500_000, "existing_debt": 15000,
            },
            "errors": [],
        })
    for key in ("credit_analysis", "property_analysis", "compliance_analysis", "decision"):
        assert result.get(key), key
