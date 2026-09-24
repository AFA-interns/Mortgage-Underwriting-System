from app.compliance.nhb_priority_sector import check_nhb

CONFIG = {"nhb_priority_sector": {"metro_ceiling": 3500000, "non_metro_ceiling": 2500000}}


def test_within_metro_ceiling_eligible():
    data = {"loan_meta": {"loan_amount": 3000000, "property_city_tier": "metro"}}
    result, flags = check_nhb(data, CONFIG)
    assert result["priority_sector_eligible"] is True
    assert result["status"] == "PASS"
    assert flags == []


def test_exceeds_metro_ceiling_not_eligible_but_not_critical():
    data = {"loan_meta": {"loan_amount": 4000000, "property_city_tier": "metro"}}
    result, flags = check_nhb(data, CONFIG)
    assert result["priority_sector_eligible"] is False
    assert result["status"] == "PASS"  # informational, never fails the check itself
    assert len(flags) == 1
    assert flags[0].severity.value not in ("CRITICAL",)


def test_missing_data_does_not_classify():
    result, flags = check_nhb({"loan_meta": {}}, CONFIG)
    assert result["priority_sector_eligible"] is None
    assert flags == []


def test_non_metro_ceiling_applies():
    data = {"loan_meta": {"loan_amount": 2000000, "property_city_tier": "non_metro"}}
    result, flags = check_nhb(data, CONFIG)
    assert result["priority_sector_eligible"] is True
