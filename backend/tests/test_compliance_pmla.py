from app.compliance.pmla_aml import check_pmla_source_of_funds

CONFIG = {
    "pmla_aml": {
        "require_source_of_funds_declaration": True,
        "require_identity_verification_log": True,
    }
}


def test_both_declared_passes():
    data = {"pmla": {"source_of_funds_declared": True, "identity_verification_logged": True}}
    result, flags = check_pmla_source_of_funds(data, CONFIG)
    assert result["status"] == "PASS"
    assert flags == []


def test_missing_source_of_funds_fails_critical():
    data = {"pmla": {"source_of_funds_declared": False, "identity_verification_logged": True}}
    result, flags = check_pmla_source_of_funds(data, CONFIG)
    assert result["status"] == "FAIL"
    assert flags[0].code == "PMLA_SOURCE_OF_FUNDS_MISSING"
    assert flags[0].severity.value == "CRITICAL"


def test_missing_identity_log_is_warning_only():
    data = {"pmla": {"source_of_funds_declared": True, "identity_verification_logged": False}}
    result, flags = check_pmla_source_of_funds(data, CONFIG)
    assert result["status"] == "WARNING"
    assert flags[0].code == "PMLA_IDENTITY_LOG_MISSING"
    assert flags[0].severity.value != "CRITICAL"


def test_no_data_at_all_fails_critical():
    result, flags = check_pmla_source_of_funds({"pmla": {}}, CONFIG)
    assert result["status"] == "FAIL"
    assert any(f.code == "PMLA_SOURCE_OF_FUNDS_MISSING" for f in flags)
