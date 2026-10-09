"""Human-in-the-loop field overrides.

A reviewer can see what each document extracted, and if OCR or regex
extraction got something wrong, correct it — the correction is a patch
applied to the already-extracted entity, not a re-parse. Applied once, by
DocumentIngestionAgent.process_document_bundle, right after Step 4
(structured extraction) and before Step 5 (validation), so validation,
reconciliation, confidence scoring and every downstream agent (credit,
property, compliance, decision) see the corrected value — exactly as if
the extractor had gotten it right the first time.

EDITABLE_FIELDS is a closed whitelist: only scalar fields a reviewer could
plausibly need to fix (names, numbers, dates, ids) are editable. Never
`provenance`, computed flags (`is_valid_format`, `is_arithmetically_valid`,
`is_recent`, ...), or nested lists — those are recomputed by validation,
not something to hand-edit.
"""
from __future__ import annotations

from typing import Any

from app.models.document_ingestion import DocumentType

EDITABLE_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.PAN_CARD: ("pan_number", "full_name", "father_name", "dob"),
    DocumentType.AADHAAR_CARD: ("aadhaar_number", "full_name", "dob", "gender", "address", "pincode"),
    DocumentType.SALARY_SLIP: (
        "employer_name", "employee_name", "employee_id", "designation", "month_year",
        "gross_salary", "net_salary", "total_deductions",
    ),
    DocumentType.FORM_16: (
        "employer_name", "employer_tan", "employee_name", "employee_pan",
        "assessment_year", "financial_year", "gross_salary_sec17_1",
        "total_deductions_chapter_via", "taxable_income", "tax_deducted_total",
    ),
    DocumentType.ITR: (
        "acknowledgement_number", "pan_number", "assessment_year", "form_type",
        "gross_total_income", "total_deductions", "total_taxable_income",
        "total_tax_paid", "filing_date",
    ),
    DocumentType.BANK_STATEMENT: (
        "bank_name", "account_holder_name", "account_number", "ifsc_code",
        "average_monthly_balance", "closing_balance", "average_monthly_salary_credit",
        "total_monthly_obligations",
    ),
    DocumentType.PROPERTY_DEED: (
        "property_address", "locality", "city", "state", "pincode", "property_type",
        "super_builtup_area_sqft", "carpet_area_sqft", "purchase_or_market_value",
        "seller_or_builder_name", "buyer_or_owner_name", "registration_number",
    ),
}


def editable_fields_for(doc_type: DocumentType) -> tuple[str, ...]:
    return EDITABLE_FIELDS.get(doc_type, ())


def validate_overrides(doc_type: DocumentType, overrides: dict[str, Any]) -> dict[str, str]:
    """Returns {field: reason} for every override key that isn't editable
    for this document type. Empty dict means the overrides are all valid."""
    allowed = set(editable_fields_for(doc_type))
    return {
        field: f"'{field}' is not an editable field for {doc_type.value}."
        for field in overrides
        if field not in allowed
    }


def apply_overrides(entity: Any, overrides: dict[str, Any]) -> list[str]:
    """Patches `entity` (a PANCardData / SalarySlipData / ... instance) in
    place with the given {field: value} overrides, restricted to that
    document type's whitelist. Returns the field names actually applied.
    Unknown fields are silently skipped here — callers that need to reject
    them should call validate_overrides first (the HTTP endpoint does)."""
    model_fields = type(entity).model_fields
    applied: list[str] = []
    for field, value in overrides.items():
        if field not in model_fields:
            continue
        setattr(entity, field, value)
        applied.append(field)
        if "provenance" in model_fields and field in entity.provenance:
            prov = entity.provenance[field]
            prov.confidence = 1.0
            prov.raw_snippet = f"Human-reviewed override: {value!r}"
    return applied
