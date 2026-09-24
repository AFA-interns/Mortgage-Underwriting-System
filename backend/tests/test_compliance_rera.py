from app.compliance.rera_check import check_rera

CONFIG = {"rera": {"required_for_under_construction": True}}


def test_not_under_construction_is_not_applicable():
    data = {"property": {"under_construction": False, "rera_status": "unknown"}}
    result, flags = check_rera(data, CONFIG)
    assert result["status"] == "NOT_APPLICABLE"
    assert flags == []


def test_under_construction_and_registered_passes():
    data = {"property": {"under_construction": True, "rera_status": "REGISTERED"}}
    result, flags = check_rera(data, CONFIG)
    assert result["status"] == "PASS"
    assert result["registered"] is True
    assert flags == []


def test_under_construction_and_not_registered_fails_critical():
    data = {"property": {"under_construction": True, "rera_status": "unknown"}}
    result, flags = check_rera(data, CONFIG)
    assert result["status"] == "FAIL"
    assert result["registered"] is False
    assert flags[0].code == "RERA_NOT_REGISTERED"
    assert flags[0].severity.value == "CRITICAL"


def test_check_disabled_via_config_always_passes():
    config = {"rera": {"required_for_under_construction": False}}
    data = {"property": {"under_construction": True, "rera_status": "unknown"}}
    result, flags = check_rera(data, config)
    assert result["status"] == "PASS"
    assert flags == []
