import app.graph.nodes.compliance as compliance_node_module
from app.graph.nodes.compliance import compliance_node


def _patch_reasoning(monkeypatch, text="stubbed reasoning"):
    monkeypatch.setattr(
        compliance_node_module, "run_compliance_reasoning", lambda rule_results: text
    )


def _clean_state():
    return {
        "application_id": "APP-001",
        "borrower_profile": {
            "loan_amount": 3000000,
            "property_city_tier": "metro",
        },
        "document_analysis": {
            "kyc": {
                "documents": [
                    {"doc_type": "PAN", "present": True},
                    {"doc_type": "AADHAAR", "present": True},
                    {"doc_type": "ADDRESS_PROOF", "present": True},
                ],
                "pmla": {
                    "source_of_funds_declared": True,
                    "identity_verification_logged": True,
                },
            },
            "borrower_identity": {
                "application_form_name": "Priya Sharma",
                "pan_card_name": "Priya Sharma",
                "aadhaar_name": "Priya Sharma",
            },
        },
        "property_analysis": {"under_construction": False, "rera_status": "unknown"},
    }


def test_clean_application_produces_pass_with_no_critical_flags(monkeypatch):
    _patch_reasoning(monkeypatch)
    state = compliance_node(_clean_state())
    result = state["compliance_analysis"]

    assert result["kyc_cdd"]["status"] == "PASS"
    assert result["rbi_fair_practices"]["status"] == "PASS"
    assert result["pmla_source_of_funds"]["status"] == "PASS"
    assert result["critical_flags"] == []
    assert result["confidence"] == 0.90


def test_incomplete_kyc_produces_critical_flag(monkeypatch):
    _patch_reasoning(monkeypatch)
    state = _clean_state()
    state["document_analysis"]["kyc"]["documents"] = [{"doc_type": "PAN", "present": True}]

    result = compliance_node(state)["compliance_analysis"]
    assert result["kyc_cdd"]["status"] == "FAIL"
    assert any("KYC_INCOMPLETE" in f for f in result["critical_flags"])
    assert result["confidence"] < 0.90


def test_under_construction_without_rera_produces_critical_flag(monkeypatch):
    _patch_reasoning(monkeypatch)
    state = _clean_state()
    state["property_analysis"] = {"under_construction": True, "rera_status": "unknown"}

    result = compliance_node(state)["compliance_analysis"]
    assert result["rera"]["status"] == "FAIL"
    assert any("RERA_NOT_REGISTERED" in f for f in result["critical_flags"])


def test_missing_upstream_data_does_not_crash_and_flags_kyc(monkeypatch):
    """No short-circuit like credit_node — missing document_analysis simply
    flows through as missing KYC docs, which is the correct SUSPEND-worthy
    outcome per the design report."""
    _patch_reasoning(monkeypatch)
    result = compliance_node({"application_id": "APP-EMPTY"})["compliance_analysis"]
    assert result["kyc_cdd"]["status"] == "FAIL"
    assert len(result["critical_flags"]) >= 1


def test_evidence_includes_reasoning_entry(monkeypatch):
    _patch_reasoning(monkeypatch, text="a specific explanation")
    result = compliance_node(_clean_state())["compliance_analysis"]
    reasoning_entries = [e for e in result["evidence"] if e["field"] == "reasoning"]
    assert len(reasoning_entries) == 1
    assert reasoning_entries[0]["value"] == "a specific explanation"


def test_output_matches_compliance_analysis_result_shape(monkeypatch):
    """Guards against drift from app.models.decision.ComplianceAnalysisResult."""
    from app.models.decision import ComplianceAnalysisResult

    _patch_reasoning(monkeypatch)
    result = compliance_node(_clean_state())["compliance_analysis"]
    # Will raise if the node's output doesn't validate against the shared model.
    ComplianceAnalysisResult(**result)
