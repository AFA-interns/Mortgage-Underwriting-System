from app.compliance.identity_consistency import check_identity_consistency

CONFIG = {"fuzzy_match": {"name_match_threshold": 90}}


def test_matching_names_pass():
    data = {
        "identity": {
            "application_form_name": "Ramesh Kumar",
            "pan_card_name": "Ramesh Kumar",
            "aadhaar_name": "Ramesh Kumar",
        }
    }
    status, flags = check_identity_consistency(data, CONFIG)
    assert status == "PASS"
    assert flags == []


def test_minor_formatting_difference_still_passes():
    data = {
        "identity": {
            "application_form_name": "Ramesh Kumar Singh",
            "pan_card_name": "Kumar Singh Ramesh",  # reordered, still same tokens
        }
    }
    status, flags = check_identity_consistency(data, CONFIG)
    assert status == "PASS"


def test_name_mismatch_gives_warning_not_fail():
    data = {
        "identity": {
            "application_form_name": "Ramesh Kumar",
            "pan_card_name": "Totally Different Person",
        }
    }
    status, flags = check_identity_consistency(data, CONFIG)
    assert status == "WARNING"
    assert any(f.code == "IDENTITY_MISMATCH_NAME" for f in flags)
    assert all(f.severity.value != "CRITICAL" for f in flags)


def test_pan_number_mismatch_fails_critical():
    data = {
        "identity": {
            "application_form_name": "Ramesh Kumar",
            "application_form_pan_number": "ABCDE1234F",
            "pan_card_name": "Ramesh Kumar",
            "pan_card_number": "ZZZZZ9999Z",
        }
    }
    status, flags = check_identity_consistency(data, CONFIG)
    assert status == "FAIL"
    assert any(f.code == "IDENTITY_MISMATCH_PAN" and f.severity.value == "CRITICAL" for f in flags)


def test_missing_data_is_not_a_mismatch():
    status, flags = check_identity_consistency({"identity": {}}, CONFIG)
    assert status == "PASS"
    assert flags == []
