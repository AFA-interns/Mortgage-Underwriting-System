from app.compliance.kyc_checks import check_kyc_cdd

CONFIG = {"required_kyc_documents": ["PAN", "AADHAAR", "ADDRESS_PROOF"]}


def _doc(doc_type, present=True, valid=True, readable=True):
    return {"doc_type": doc_type, "present": present, "valid": valid, "readable": readable}


def test_all_documents_present_passes():
    data = {"kyc_documents": [_doc("PAN"), _doc("AADHAAR"), _doc("ADDRESS_PROOF")]}
    result, flags = check_kyc_cdd(data, CONFIG)
    assert result["status"] == "PASS"
    assert result["missing_documents"] == []
    assert flags == []


def test_missing_document_fails_and_flags():
    data = {"kyc_documents": [_doc("PAN"), _doc("AADHAAR")]}
    result, flags = check_kyc_cdd(data, CONFIG)
    assert result["status"] == "FAIL"
    assert "ADDRESS_PROOF" in result["missing_documents"]
    assert len(flags) == 1
    assert flags[0].code == "KYC_INCOMPLETE"
    assert flags[0].severity.value == "CRITICAL"


def test_invalid_document_counts_as_missing():
    data = {
        "kyc_documents": [
            _doc("PAN", valid=False),
            _doc("AADHAAR"),
            _doc("ADDRESS_PROOF"),
        ]
    }
    result, flags = check_kyc_cdd(data, CONFIG)
    assert result["status"] == "FAIL"
    assert "PAN" in result["missing_documents"]
    assert flags[0].code == "KYC_INCOMPLETE"


def test_no_documents_at_all_fails():
    result, flags = check_kyc_cdd({"kyc_documents": []}, CONFIG)
    assert result["status"] == "FAIL"
    assert set(result["missing_documents"]) == {"PAN", "AADHAAR", "ADDRESS_PROOF"}
    assert len(flags) == 3
