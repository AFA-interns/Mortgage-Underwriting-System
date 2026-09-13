"""
Comprehensive Automated Pytest Suite for Document Ingestion Agent.
Tests:
- Classification accuracy for Indian mortgage documents
- Deterministic validators (PAN, Aadhaar, IFSC, Salary arithmetic)
- Cross-document entity reconciliation (Names, Income vs Bank credits, Employer)
- End-to-end 7-step pipeline execution across all 4 scenarios
- LangGraph node input/output state compatibility
"""

import os
import pytest
from src.models.schemas import DocumentType
from src.document_ingestion.preprocessor import DocumentPreprocessor
from src.document_ingestion.classifier import DocumentClassifier
from src.document_ingestion.validators import IndianDocumentValidators
from src.document_ingestion.reconciliation import CrossDocumentReconciler, _compute_string_similarity
from src.document_ingestion.agent import DocumentIngestionAgent, document_ingestion_node
from src.mock_data.generate_docs import generate_all_mock_scenarios


@pytest.fixture(scope="session")
def mock_docs():
    """Generates and returns paths to all mock test document suites."""
    return generate_all_mock_scenarios()


# -----------------------------------------------------------------
# 1. Validation Unit Tests
# -----------------------------------------------------------------

def test_pan_validator_valid():
    res = IndianDocumentValidators.validate_pan("ABCPS1234F", last_name="Sharma")
    assert res.is_valid is True
    assert res.severity in ["INFO", "WARNING"]


def test_pan_validator_invalid_format():
    res = IndianDocumentValidators.validate_pan("INVALID_PAN_123")
    assert res.is_valid is False
    assert res.severity == "ERROR"


def test_aadhaar_validator_masked():
    res = IndianDocumentValidators.validate_aadhaar("XXXX-XXXX-8921")
    assert res.is_valid is True


def test_aadhaar_validator_invalid():
    res = IndianDocumentValidators.validate_aadhaar("1234")
    assert res.is_valid is False


def test_ifsc_validator():
    res_valid = IndianDocumentValidators.validate_ifsc("HDFC0001234")
    assert res_valid.is_valid is True

    res_invalid = IndianDocumentValidators.validate_ifsc("INVALID_IFSC")
    assert res_invalid.is_valid is False


def test_salary_arithmetic_reconciled():
    res = IndianDocumentValidators.validate_salary_arithmetic(
        gross_salary=150000.0,
        net_salary=124600.0,
        total_deductions=25400.0
    )
    assert res.is_valid is True


def test_salary_arithmetic_discrepancy():
    res = IndianDocumentValidators.validate_salary_arithmetic(
        gross_salary=150000.0,
        net_salary=90000.0,
        total_deductions=25400.0
    )
    assert res.is_valid is False
    assert "Payslip arithmetic mismatch" in res.message


# -----------------------------------------------------------------
# 2. String Similarity & Cross-Reconciliation Tests
# -----------------------------------------------------------------

def test_string_similarity_exact():
    score = _compute_string_similarity("Aarav Sharma", "Aarav Sharma")
    assert score >= 0.98


def test_string_similarity_fuzzy_initials():
    score = _compute_string_similarity("Priya Suresh Patel", "Priya S Patel")
    assert score >= 0.75


def test_string_similarity_mismatch():
    score = _compute_string_similarity("Aarav Sharma", "Vikram Malhotra")
    assert score < 0.30


# -----------------------------------------------------------------
# 3. Document Classification Tests
# -----------------------------------------------------------------

def test_document_classification(mock_docs):
    prime_files = mock_docs["clean_prime"]
    for path in prime_files:
        prep = DocumentPreprocessor.process_file(path)
        doc_type, conf = DocumentClassifier.classify(prep)
        assert doc_type != DocumentType.UNKNOWN
        assert conf >= 0.60


# -----------------------------------------------------------------
# 4. Scenario 1: Clean Prime End-to-End Test
# -----------------------------------------------------------------

def test_scenario_1_clean_prime(mock_docs):
    files = mock_docs["clean_prime"]
    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id="TEST-APP-001"
    )

    # 1. KYC verification
    assert output.borrower_kyc is not None
    assert output.borrower_kyc.primary_name == "Aarav Sharma"
    assert output.borrower_kyc.pan_number == "ABCPS1234F"
    assert "560066" in str(output.borrower_kyc.residential_address)

    # 2. Income verification
    assert output.borrower_income is not None
    assert output.borrower_income.monthly_gross_salary == 150000.0
    assert output.borrower_income.monthly_net_salary == 124600.0
    assert output.borrower_income.salary_slips_provided_count == 3

    # 3. Banking & Liabilities
    assert output.borrower_liabilities is not None
    assert output.borrower_liabilities.detected_monthly_emis == 15000.0
    assert output.borrower_liabilities.cheque_bounce_count_6m == 0

    # 4. Property Profile
    assert output.property_profile is not None
    assert output.property_profile.purchase_or_market_value == 12500000.0
    assert output.property_profile.super_builtup_area_sqft == 1450.0

    # 5. Completeness & Confidence
    assert output.checklist.is_complete is True
    assert output.confidence.overall_confidence >= 0.90
    assert output.confidence.confidence_level == "HIGH"
    assert output.human_review.requires_human_review is False


# -----------------------------------------------------------------
# 5. Scenario 2: Name Discrepancy Test
# -----------------------------------------------------------------

def test_scenario_2_name_discrepancy(mock_docs):
    files = mock_docs["name_discrepancy"]
    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id="TEST-APP-002"
    )

    assert len(output.reconciliation.contradictions) > 0
    assert output.human_review.requires_human_review is True
    assert output.human_review.review_priority in ["HIGH", "CRITICAL"]


# -----------------------------------------------------------------
# 6. Scenario 3: Salary vs Bank Credit Discrepancy Test
# -----------------------------------------------------------------

def test_scenario_3_salary_discrepancy(mock_docs):
    files = mock_docs["salary_discrepancy"]
    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id="TEST-APP-003"
    )

    # Bank credited 85k, payslip claims 160k
    assert any("Income discrepancy" in c for c in output.reconciliation.contradictions)
    assert output.human_review.requires_human_review is True


# -----------------------------------------------------------------
# 7. Scenario 4: Missing Mandatory Documents Test
# -----------------------------------------------------------------

def test_scenario_4_missing_docs(mock_docs):
    files = mock_docs["missing_docs"]
    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=files,
        application_id="TEST-APP-004"
    )

    assert output.checklist.is_complete is False
    assert len(output.checklist.missing_mandatory_documents) >= 2
    assert output.human_review.requires_human_review is True


# -----------------------------------------------------------------
# 8. LangGraph Node Interface Test
# -----------------------------------------------------------------

def test_langgraph_node_execution(mock_docs):
    input_state = {
        "application_id": "LG-TEST-APP-100",
        "borrower_id": "BORR-100",
        "raw_document_paths": mock_docs["clean_prime"],
    }

    updated_state = document_ingestion_node(input_state)

    assert updated_state["application_id"] == "LG-TEST-APP-100"
    assert "doc_ingestion_output" in updated_state
    assert updated_state["current_step"] == "CREDIT_AND_PROPERTY_ANALYSIS"
    assert updated_state["status"] == "IN_PROGRESS"

    doc_out = updated_state["doc_ingestion_output"]
    assert doc_out["borrower_kyc"]["primary_name"] == "Aarav Sharma"
    assert doc_out["borrower_income"]["monthly_gross_salary"] == 150000.0
