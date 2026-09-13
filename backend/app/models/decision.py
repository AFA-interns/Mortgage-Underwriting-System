"""Pydantic models for the Decision Agent."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ──────────────────────────────────────────────────────────────────────

class DecisionType(StrEnum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    SUSPEND = "SUSPEND"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    PENDING_REVIEW = "PENDING_REVIEW"


class CreditDecisionType(StrEnum):
    """The Credit Analysis Agent's own preliminary decision — NOT the final
    loan decision (that remains DecisionType, owned by the Decision Agent)."""
    APPROVE = "APPROVE"
    CONDITIONAL = "CONDITIONAL"
    REJECT = "REJECT"


class CrewRole(StrEnum):
    UNDERWRITER = "underwriter"
    RISK_ANALYST = "risk_analyst"
    REPORT_WRITER = "report_writer"


# ── Evidence / Provenance ─────────────────────────────────────────────────────

class Evidence(BaseModel):
    agent: str = ""
    field: str = ""
    value: Any = None
    source: str = ""
    timestamp: datetime | None = None
    confidence: float | None = Field(None, ge=0, le=1)


# ── Input Analysis Results ────────────────────────────────────────────────────

class DocumentAnalysisResult(BaseModel):
    verification_status: str = "unknown"
    documents: list[dict[str, Any]] = Field(default_factory=list)
    borrower_identity: dict[str, Any] = Field(default_factory=dict)
    income: dict[str, Any] = Field(default_factory=dict)
    assets: dict[str, Any] = Field(default_factory=dict)
    liabilities: dict[str, Any] = Field(default_factory=dict)
    kyc: dict[str, Any] = Field(default_factory=dict)
    missing_documents: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    provenance: list[Evidence] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class CreditAnalysisResult(BaseModel):
    cibil_score: int | None = Field(None, ge=0, le=900)
    credit_risk_tier: str = "unknown"
    # Finer-grained CIBIL band than credit_risk_tier's low/moderate/high -
    # one of Excellent/Good/Fair/Poor/Very Poor/New-to-Credit. Additive field,
    # not read by the existing risk engine/crew - see README_credit.md.
    credit_band: str = "unknown"
    foir: float | None = Field(None, ge=0, le=1)
    monthly_obligations: float = 0.0
    ltv: float | None = Field(None, ge=0, le=2)
    income_stability: str = "unknown"
    confidence: float = Field(0.0, ge=0, le=1)
    # Credit Analysis Agent's own 0-100 composite (credit_band + FOIR headroom
    # + red flags) - distinct from the Decision Agent's separate 6-component
    # app.decision.risk_engine score, which consumes this agent's other
    # fields (cibil_score, credit_risk_tier, foir, ltv, income_stability) as
    # one of its own inputs rather than reusing this number directly.
    risk_score: float = Field(0.0, ge=0, le=100)
    # Rule-based preliminary credit decision - explained, never overridden,
    # by this agent's LLM reasoning node. NOT the final loan decision.
    preliminary_decision: CreditDecisionType | None = None
    reasoning: str = ""
    flags: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class PropertyAnalysisResult(BaseModel):
    estimated_value: float = 0.0
    market_range_low: float = 0.0
    market_range_high: float = 0.0
    valuation_confidence: float = Field(0.0, ge=0, le=1)
    price_per_sqft: float = 0.0
    comparables: list[dict[str, Any]] = Field(default_factory=list)
    registry_circle_rate_comparison: dict[str, Any] = Field(default_factory=dict)
    valuation_variance_percent: float = 0.0
    rera_status: str = "unknown"
    flags: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class ComplianceAnalysisResult(BaseModel):
    kyc_cdd: dict[str, Any] = Field(default_factory=dict)
    identity_consistency: str = "unknown"
    pmla_source_of_funds: dict[str, Any] = Field(default_factory=dict)
    rbi_fair_practices: dict[str, Any] = Field(default_factory=dict)
    nhb: dict[str, Any] = Field(default_factory=dict)
    rera: dict[str, Any] = Field(default_factory=dict)
    rule_status: dict[str, str] = Field(default_factory=dict)
    critical_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)


class BorrowerProfile(BaseModel):
    application_id: str = ""
    name: str = ""
    age: int | None = None
    monthly_income: float = 0.0
    employment_type: str = ""
    employer: str = ""
    loan_amount: float = 0.0
    loan_tenure_months: int = 0
    property_value: float = 0.0
    existing_debt: float = 0.0


# ── Decision Agent Internal Results ────────────────────────────────────────────

class ValidationResult(BaseModel):
    is_complete: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    upstream_status: dict[str, str] = Field(default_factory=dict)


class Contradiction(BaseModel):
    field: str
    severity: Severity
    sources: list[dict[str, Any]] = Field(default_factory=list)
    resolution: ResolutionStatus = ResolutionStatus.UNRESOLVED
    description: str = ""


class AgentComparison(BaseModel):
    assessments_compared: list[str] = Field(default_factory=list)
    confidence_comparison: dict[str, float] = Field(default_factory=dict)
    agreement_fields: list[str] = Field(default_factory=list)
    disagreement_fields: list[str] = Field(default_factory=list)
    material_disagreement: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class RiskComponent(BaseModel):
    name: str
    weight: float
    raw_score: float = Field(0.0, ge=0, le=100)
    weighted_score: float = 0.0
    factors: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    score: float = Field(0.0, ge=0, le=100)
    level: RiskLevel = RiskLevel.VERY_HIGH
    components: list[RiskComponent] = Field(default_factory=list)
    key_positive_factors: list[str] = Field(default_factory=list)
    key_risk_factors: list[str] = Field(default_factory=list)
    calculation_failed: bool = False


class ConfidenceAssessment(BaseModel):
    score: float = Field(0.0, ge=0, le=1)
    factors: dict[str, float] = Field(default_factory=dict)
    below_threshold: bool = True
    reasoning: str = ""


class CrewMemberOutput(BaseModel):
    role: CrewRole
    recommendation: DecisionType | None = None
    confidence: float = Field(0.0, ge=0, le=1)
    reasoning: str = ""
    key_factors: list[str] = Field(default_factory=list)
    risks_identified: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class DecisionCrewOutput(BaseModel):
    underwriter: CrewMemberOutput | None = None
    risk_analyst: CrewMemberOutput | None = None
    report_writer: CrewMemberOutput | None = None
    execution_time_seconds: float = 0.0
    error: str | None = None


# ── Final Output ───────────────────────────────────────────────────────────────

class DecisionResult(BaseModel):
    application_id: str
    decision: DecisionType
    risk_score: float = Field(0.0, ge=0, le=100)
    risk_level: RiskLevel = RiskLevel.VERY_HIGH
    confidence: float = Field(0.0, ge=0, le=1)
    key_positive_factors: list[str] = Field(default_factory=list)
    key_risk_factors: list[str] = Field(default_factory=list)
    compliance_status: str = "PENDING"
    human_review_required: bool = True
    rationale: str = ""
    agent_consensus: dict[str, Any] = Field(default_factory=dict)
    report_required: bool = True
    evidence: list[Evidence] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    errors: list[str] = Field(default_factory=list)


class UnderwritingReport(BaseModel):
    application_id: str
    decision: DecisionType
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    application_summary: dict[str, Any] = Field(default_factory=dict)
    borrower_summary: dict[str, Any] = Field(default_factory=dict)
    document_verification: dict[str, Any] = Field(default_factory=dict)
    credit_assessment: dict[str, Any] = Field(default_factory=dict)
    foir_ltv: dict[str, Any] = Field(default_factory=dict)
    property_valuation: dict[str, Any] = Field(default_factory=dict)
    compliance: dict[str, Any] = Field(default_factory=dict)
    risk_score_section: dict[str, Any] = Field(default_factory=dict)
    confidence_section: dict[str, Any] = Field(default_factory=dict)
    positive_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    final_recommendation: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    human_review_status: str = "NOT_REQUIRED"
    disclaimer: str = (
        "This is a decision-support/pre-screening output. "
        "It does not constitute a final lending decision. "
        "Human accountability remains mandatory."
    )


class AuditRecord(BaseModel):
    application_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_versions: dict[str, str] = Field(default_factory=dict)
    upstream_outputs: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationResult | None = None
    contradictions: list[Contradiction] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    confidence_assessment: ConfidenceAssessment | None = None
    crew_output: DecisionCrewOutput | None = None
    final_decision: DecisionResult | None = None
    rationale: str = ""
    human_review_status: str = "PENDING"
    reviewer_action: str | None = None
    errors: list[str] = Field(default_factory=list)
