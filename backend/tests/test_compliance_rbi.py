from app.compliance.rbi_fair_practices import check_rbi_fair_practices

CONFIG = {"protected_attributes": ["religion", "caste", "gender", "region"]}


def test_clean_fields_pass():
    data = {"raw_fields": {"name": "Ramesh", "loan_amount": 5000000}}
    result, flags = check_rbi_fair_practices(data, CONFIG)
    assert result["status"] == "PASS"
    assert flags == []


def test_protected_attribute_present_fails_critical():
    data = {"raw_fields": {"name": "Ramesh", "religion": "some_value"}}
    result, flags = check_rbi_fair_practices(data, CONFIG)
    assert result["status"] == "FAIL"
    assert "religion" in result["protected_attributes_detected"]
    assert len(flags) == 1
    assert flags[0].code == "PROTECTED_ATTRIBUTE_USED"
    assert flags[0].severity.value == "CRITICAL"


def test_case_insensitive_detection():
    data = {"raw_fields": {"Religion": "x"}}
    result, flags = check_rbi_fair_practices(data, CONFIG)
    assert result["status"] == "FAIL"


def test_multiple_protected_attributes_all_flagged():
    data = {"raw_fields": {"gender": "x", "caste": "y"}}
    result, flags = check_rbi_fair_practices(data, CONFIG)
    assert len(flags) == 2
    assert set(result["protected_attributes_detected"]) == {"gender", "caste"}
