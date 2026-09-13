"""
Domain data models and schemas for Indian Mortgage Underwriting System.
Covers PAN, Aadhaar, Salary Slips, Form 16, ITR-V, Bank Statements, Property Deeds,
Field Provenance, and Extraction Confidence.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date, datetime


class DocumentType(str, Enum):
    PAN_CARD = "PAN_CARD"
    AADHAAR_CARD = "AADHAAR_CARD"
    SALARY_SLIP = "SALARY_SLIP"
    FORM_16 = "FORM_16"
    ITR = "ITR"
    BANK_STATEMENT = "BANK_STATEMENT"
    PROPERTY_DEED = "PROPERTY_DEED"
    UNKNOWN = "UNKNOWN"


class FieldProvenance(BaseModel):
    source_document: str = Field(description="Filename or identifier of the source document")
    page_number: int = Field(default=1, description="Page number where the field was located")
    raw_snippet: Optional[str] = Field(default=None, description="Exact raw text snippet extracted from OCR/PDF")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score for this field")


class PANCardData(BaseModel):
    pan_number: Optional[str] = Field(default=None, description="10-character alphanumeric PAN")
    full_name: Optional[str] = Field(default=None, description="Name printed on the PAN card")
    father_name: Optional[str] = Field(default=None, description="Father's name")
    dob: Optional[str] = Field(default=None, description="Date of birth in DD/MM/YYYY or YYYY-MM-DD format")
    entity_type: Optional[str] = Field(default="Individual", description="Entity type inferred from 4th character (P=Individual)")
    is_valid_format: bool = Field(default=False, description="Whether PAN adheres to Indian Income Tax format")
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class AadhaarCardData(BaseModel):
    aadhaar_number: Optional[str] = Field(default=None, description="Masked or full 12-digit Aadhaar number")
    full_name: Optional[str] = Field(default=None, description="Name as registered on Aadhaar")
    dob: Optional[str] = Field(default=None, description="Date of birth or Year of birth")
    gender: Optional[str] = Field(default=None, description="Gender (Male / Female / Other)")
    address: Optional[str] = Field(default=None, description="Full residential address")
    pincode: Optional[str] = Field(default=None, description="6-digit Indian Postal PIN code")
    is_masked: bool = Field(default=True, description="Indicates if first 8 digits are masked (e.g., XXXX-XXXX-1234)")
    is_valid_format: bool = Field(default=False)
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class SalaryEarningItem(BaseModel):
    component: str = Field(description="e.g. Basic, HRA, Special Allowance, Conveyance")
    amount: float = Field(default=0.0)


class SalaryDeductionItem(BaseModel):
    component: str = Field(description="e.g. Providend Fund (PF), Professional Tax, TDS, Loan Deductions")
    amount: float = Field(default=0.0)


class SalarySlipData(BaseModel):
    employer_name: Optional[str] = Field(default=None, description="Company / Employer legal name")
    employee_name: Optional[str] = Field(default=None, description="Employee full name")
    employee_id: Optional[str] = Field(default=None, description="Employee code / ID")
    designation: Optional[str] = Field(default=None, description="Job title / designation")
    month_year: Optional[str] = Field(default=None, description="e.g. June 2026 or 06/2026")
    pay_period_start: Optional[str] = None
    pay_period_end: Optional[str] = None
    gross_salary: float = Field(default=0.0, description="Gross monthly earnings before deductions")
    net_salary: float = Field(default=0.0, description="Take-home pay credited to bank")
    total_deductions: float = Field(default=0.0, description="Sum of all monthly deductions")
    earnings_breakdown: List[SalaryEarningItem] = Field(default_factory=list)
    deductions_breakdown: List[SalaryDeductionItem] = Field(default_factory=list)
    bank_account_number_hint: Optional[str] = Field(default=None, description="Disbursal bank account suffix or number")
    pan_number_hint: Optional[str] = None
    is_arithmetically_valid: bool = Field(default=False, description="Gross == Net + Deductions within tolerance")
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class Form16Data(BaseModel):
    employer_name: Optional[str] = Field(default=None, description="Deductor / Employer Name")
    employer_tan: Optional[str] = Field(default=None, description="Employer 10-character TAN")
    employee_name: Optional[str] = Field(default=None, description="Employee full name")
    employee_pan: Optional[str] = Field(default=None, description="Employee PAN number")
    assessment_year: Optional[str] = Field(default=None, description="e.g. 2026-27")
    financial_year: Optional[str] = Field(default=None, description="e.g. 2025-26")
    gross_salary_sec17_1: float = Field(default=0.0, description="Gross salary under section 17(1)")
    total_deductions_chapter_via: float = Field(default=0.0, description="Deductions under 80C, 80D, etc.")
    taxable_income: float = Field(default=0.0, description="Net taxable income")
    tax_deducted_total: float = Field(default=0.0, description="Total TDS deposited")
    is_valid_format: bool = Field(default=False)
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class ITRVData(BaseModel):
    acknowledgement_number: Optional[str] = Field(default=None)
    pan_number: Optional[str] = Field(default=None)
    assessment_year: Optional[str] = Field(default=None)
    form_type: Optional[str] = Field(default="ITR-1", description="e.g. ITR-1, ITR-2, ITR-4")
    gross_total_income: float = Field(default=0.0)
    total_deductions: float = Field(default=0.0)
    total_taxable_income: float = Field(default=0.0)
    total_tax_paid: float = Field(default=0.0)
    filing_date: Optional[str] = None
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class BankTransactionSummary(BaseModel):
    date: str
    description: str
    amount: float
    type: str = Field(description="'CREDIT' or 'DEBIT'")
    category: Optional[str] = Field(default=None, description="'SALARY', 'LOAN_EMI', 'INTEREST', 'OTHER'")


class BankStatementData(BaseModel):
    bank_name: Optional[str] = Field(default=None, description="e.g. HDFC Bank, SBI, ICICI Bank")
    account_holder_name: Optional[str] = Field(default=None)
    account_number: Optional[str] = Field(default=None)
    account_type: Optional[str] = Field(default="Savings", description="Savings / Current / Salary")
    ifsc_code: Optional[str] = Field(default=None)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    months_covered: int = Field(default=6)
    average_monthly_balance: float = Field(default=0.0)
    closing_balance: float = Field(default=0.0)
    salary_credits: List[BankTransactionSummary] = Field(default_factory=list, description="Detected regular monthly salary credits")
    average_monthly_salary_credit: float = Field(default=0.0)
    recurring_loan_emis: List[BankTransactionSummary] = Field(default_factory=list, description="Detected loan EMI / NACH debits")
    total_monthly_obligations: float = Field(default=0.0, description="Sum of monthly detected EMIs")
    bounce_cheque_count: int = Field(default=0, description="Inward bounce / ECS return count")
    is_valid_format: bool = Field(default=False)
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class PropertyDocData(BaseModel):
    document_title: Optional[str] = Field(default=None, description="Sale Deed, Allotment Letter, Possession Certificate")
    property_address: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    pincode: Optional[str] = Field(default=None)
    property_type: Optional[str] = Field(default="Residential Flat", description="Residential Flat, Independent House, Villa, Plot")
    seller_or_builder_name: Optional[str] = Field(default=None)
    buyer_or_owner_name: Optional[str] = Field(default=None)
    super_builtup_area_sqft: Optional[float] = Field(default=None)
    carpet_area_sqft: Optional[float] = Field(default=None)
    plot_or_flat_number: Optional[str] = Field(default=None)
    purchase_or_market_value: Optional[float] = Field(default=None, description="Transaction consideration amount in INR")
    registration_number: Optional[str] = Field(default=None)
    registration_date: Optional[str] = None
    provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    classified_type: DocumentType
    classification_confidence: float
    page_count: int = 1
    file_size_bytes: int = 0
    extracted_text_snippet: Optional[str] = None
    processing_status: str = "SUCCESS"  # SUCCESS, WARNING, ERROR
    error_message: Optional[str] = None
