"""Tests for the payslip recency check (feature: payslips must be from the
last N months, default 3)."""
from datetime import date

from app.document_ingestion.agent import DocumentIngestionAgent
from app.document_ingestion.config import get_document_ingestion_config
from app.document_ingestion.validators import IndianDocumentValidators as V
from tests.mock_data.generate_docs import generate_all_mock_scenarios

AS_OF = date(2026, 10, 3)  # fixed reference date so these tests never go stale


def test_parse_month_year_handles_common_formats():
    for text, expected in [
        ("June 2026", date(2026, 6, 1)),
        ("June-2026", date(2026, 6, 1)),
        ("June, 2026", date(2026, 6, 1)),
        ("Jun 2026", date(2026, 6, 1)),
        ("06/2026", date(2026, 6, 1)),
        ("06-2026", date(2026, 6, 1)),
    ]:
        assert V.parse_month_year(text) == expected, text


def test_parse_month_year_rejects_garbage():
    assert V.parse_month_year(None) is None
    assert V.parse_month_year("not a date") is None


def test_within_window_is_valid():
    result = V.validate_payslip_recency("August 2026", window_months=3, as_of=AS_OF)
    assert result.is_valid is True


def test_at_window_boundary_is_valid():
    result = V.validate_payslip_recency("July 2026", window_months=3, as_of=AS_OF)  # exactly 3 months old
    assert result.is_valid is True


def test_older_than_window_is_flagged():
    result = V.validate_payslip_recency("March 2026", window_months=3, as_of=AS_OF)  # 7 months old
    assert result.is_valid is False
    assert "months old" in result.message


def test_future_dated_payslip_is_flagged():
    result = V.validate_payslip_recency("December 2026", window_months=3, as_of=AS_OF)
    assert result.is_valid is False
    assert "future" in result.message.lower()


def test_missing_month_year_is_flagged_not_crashed():
    result = V.validate_payslip_recency(None)
    assert result.is_valid is False


def test_config_default_window_is_3_months():
    assert get_document_ingestion_config()["salary_slip"]["recency_window_months"] == 3


def test_clean_scenario_payslips_pass_recency_through_the_full_agent(mock_docs):
    """The bundled demo payslips are generated relative to today, so they
    must always clear the recency check end to end."""
    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=mock_docs["clean_prime"], application_id="TEST-RECENCY-001",
    )
    assert output.borrower_income is not None
    assert output.checklist.has_salary_slips
    assert output.human_review.requires_human_review is False


def test_stale_payslip_routes_to_human_review():
    """A payslip dated well outside the window is caught even when it is
    otherwise arithmetically perfect."""
    import glob
    import os
    import tempfile

    import fitz

    from tests.mock_data.generate_docs import _create_pdf_document

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "salary_slip_stale.pdf")
        _create_pdf_document(path, [{
            "title": "ACME CORP",
            "subtitle": "Payslip for January 2020",
            "sections": [{
                "heading": "Earnings",
                "items": [
                    ("Employee Name", "Test User"),
                    ("Pay Period", "January 2020"),
                    ("Gross Salary", "INR 1,00,000.00"),
                    ("Total Deductions", "INR 20,000.00"),
                    ("Net Pay", "INR 80,000.00"),
                ],
            }],
        }])
        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=[path], application_id="TEST-RECENCY-STALE",
        )
    assert output.human_review.requires_human_review is True
    assert any("recency" in r.lower() or "months old" in r.lower() for r in output.human_review.reasons)
