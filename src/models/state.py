"""
LangGraph State and Output Models for the Mortgage Underwriting System.
This defines the exact structured contract produced by the Document Ingestion Agent
and consumed by downstream agents (Credit Analysis Agent, Property Valuation Agent,
Compliance Agent, Decision Agent).
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from src.models.schemas import (
    DocumentType,
    PANCardData,
    AadhaarCardData,
    SalarySlipData,
    Form16Data,
    ITRVData,
    BankStatementData,
    PropertyDocData,
    DocumentMetadata,
)


class NameMatchResult(BaseModel):
    document_1: str
    name_1: str
    document_2: str
    name_2: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    is_match: bool
    status: str = Field(description="'EXACT_MATCH', 'FUZZY_MATCH', 'MISMATCH'")
    notes: Optional[str] = None


class SalaryReconciliationResult(BaseModel):
    salary_slip_month: str
    payslip_net_salary: float
    bank_credited_salary: float
    variance_amount: float
    variance_percentage: float
    is_reconciled: bool
    status: str = Field(description="'MATCH', 'WITHIN_TOLERANCE', 'DISCREPANCY'")
    notes: Optional[str] = None


class EmployerReconciliationResult(BaseModel):
    salary_slip_employer: Optional[str] = None
    form16_employer: Optional[str] = None
    similarity_score: float = 1.0
    is_match: bool = True
    status: str = "MATCH"


class AddressReconciliationResult(BaseModel):
    aadhaar_address: Optional[str] = None
    property_address: Optional[str] = None
    city_match: bool = True
    pincode_match: bool = True
    is_same_city: bool = True
    notes: Optional[str] = None


class CrossDocumentReconciliationReport(BaseModel):
    name_matches: List[NameMatchResult] = Field(default_factory=list)
    salary_reconciliations: List[SalaryReconciliationResult] = Field(default_factory=list)
    employer_reconciliation: Optional[EmployerReconciliationResult] = None
    address_reconciliation: Optional[AddressReconciliationResult] = None
    total_contradictions_count: int = 0
    contradictions: List[str] = Field(default_factory=list)
    reconciliation_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ConfidenceBreakdown(BaseModel):
    ocr_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    field_validation_score: float = Field(default=1.0, ge=0.0, le=1.0)
    cross_reconciliation_score: float = Field(default=1.0, ge=0.0, le=1.0)
    completeness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_level: str = Field(default="HIGH", description="'HIGH' (>=0.85), 'MEDIUM' (0.70-0.84), 'LOW' (<0.70)")


class MissingDocumentsCheck(BaseModel):
    has_pan: bool = False
    has_aadhaar: bool = False
    has_salary_slips: bool = False
    salary_slip_count: int = 0
    has_form_16: bool = False
    has_itr: bool = False
    has_bank_statement: bool = False
    bank_statement_months: int = 0
    has_property_docs: bool = False
    missing_mandatory_documents: List[str] = Field(default_factory=list)
    is_complete: bool = False


class HumanReviewRouting(BaseModel):
    requires_human_review: bool = False
    review_priority: str = Field(default="NONE", description="'NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'")
    reasons: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)


# -------------------------------------------------------------
# Clean Downstream Packages for Credit & Property Agents
# -------------------------------------------------------------

class BorrowerKYCProfile(BaseModel):
    primary_name: str
    pan_number: Optional[str] = None
    aadhaar_masked: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    residential_address: Optional[str] = None
    pincode: Optional[str] = None


class BorrowerIncomeProfile(BaseModel):
    employer_name: Optional[str] = None
    designation: Optional[str] = None
    monthly_gross_salary: float = 0.0
    monthly_net_salary: float = 0.0
    annual_gross_income_form16: float = 0.0
    annual_taxable_income: float = 0.0
    salary_slips_provided_count: int = 0
    average_bank_salary_credit: float = 0.0
    income_stability_status: str = "STABLE"


class BorrowerLiabilitiesProfile(BaseModel):
    detected_monthly_emis: float = 0.0
    active_loan_count_detected: int = 0
    cheque_bounce_count_6m: int = 0
    loan_debit_records: List[Dict[str, Any]] = Field(default_factory=list)


class PropertyProfile(BaseModel):
    property_title: Optional[str] = None
    property_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    property_type: Optional[str] = "Residential Flat"
    super_builtup_area_sqft: Optional[float] = None
    carpet_area_sqft: Optional[float] = None
    purchase_or_market_value: Optional[float] = None
    seller_or_builder_name: Optional[str] = None
    buyer_or_owner_name: Optional[str] = None
    registration_number: Optional[str] = None


# -------------------------------------------------------------
# Standard Output Passed to LangGraph Shared State
# -------------------------------------------------------------

class DocumentIngestionOutput(BaseModel):
    application_id: str
    borrower_id: Optional[str] = None
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Processed Document Entities
    documents_metadata: List[DocumentMetadata] = Field(default_factory=list)
    pan_card: Optional[PANCardData] = None
    aadhaar_card: Optional[AadhaarCardData] = None
    salary_slips: List[SalarySlipData] = Field(default_factory=list)
    form_16: Optional[Form16Data] = None
    itr_v: Optional[ITRVData] = None
    bank_statement: Optional[BankStatementData] = None
    property_document: Optional[PropertyDocData] = None
    
    # Standard Hand-offs for Downstream Agents
    borrower_kyc: Optional[BorrowerKYCProfile] = None
    borrower_income: Optional[BorrowerIncomeProfile] = None
    borrower_liabilities: Optional[BorrowerLiabilitiesProfile] = None
    property_profile: Optional[PropertyProfile] = None
    
    # Verification & Audit
    checklist: MissingDocumentsCheck = Field(default_factory=MissingDocumentsCheck)
    reconciliation: CrossDocumentReconciliationReport = Field(default_factory=CrossDocumentReconciliationReport)
    confidence: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    human_review: HumanReviewRouting = Field(default_factory=HumanReviewRouting)
    
    # Audit Trail Log
    audit_log: List[str] = Field(default_factory=list)


# -------------------------------------------------------------
# Full Multi-Agent LangGraph Shared State Definition
# -------------------------------------------------------------

class MortgageUnderwritingState(BaseModel):
    """
    Complete state container shared across the LangGraph multi-agent pipeline:
    Agent 1 (Doc Ingestion) -> Agent 2 (Credit) + Agent 3 (Property) -> Agent 4 (Compliance) -> Agent 5 (Decision)
    """
    application_id: str
    borrower_id: Optional[str] = "BORR-2026-001"
    raw_document_paths: List[str] = Field(default_factory=list)
    
    # AGENT 1: Document Ingestion Agent Output
    doc_ingestion_output: Optional[DocumentIngestionOutput] = None
    
    # AGENT 2: Credit Analysis Agent (Aryan & Lakshya)
    credit_analysis_output: Optional[Dict[str, Any]] = None
    
    # AGENT 3: Property Valuation Agent (Soojal & Yash)
    property_valuation_output: Optional[Dict[str, Any]] = None
    
    # AGENT 4: Compliance Agent (Saurav)
    compliance_output: Optional[Dict[str, Any]] = None
    
    # AGENT 5: Decision Agent (Ashfaque)
    decision_output: Optional[Dict[str, Any]] = None
    
    # Workflow control
    current_step: str = "DOCUMENT_INGESTION"
    status: str = "IN_PROGRESS"  # IN_PROGRESS, HITL_PENDING, COMPLETED, SUSPENDED
