"""Pydantic schemas for Decision Agent evaluation metrics."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.decision import DecisionResult, DecisionType

_INPUT_FIELDS = [
    "borrower_profile",
    "document_analysis",
    "credit_analysis",
    "property_analysis",
    "compliance_analysis",
]


class LabeledCase(BaseModel):
    """A single labeled underwriting case — pipeline input + ground truth label."""

    application_id: str
    borrower_profile: dict[str, Any] = Field(default_factory=dict)
    document_analysis: dict[str, Any] = Field(default_factory=dict)
    credit_analysis: dict[str, Any] = Field(default_factory=dict)
    property_analysis: dict[str, Any] = Field(default_factory=dict)
    compliance_analysis: dict[str, Any] = Field(default_factory=dict)
    ground_truth_decision: DecisionType
    outcome: str | None = None
    predicted: DecisionResult | None = None

    def as_pipeline_input(self) -> dict[str, Any]:
        """Return the case as a pipeline input dict (excludes label/prediction)."""
        data: dict[str, Any] = {"application_id": self.application_id}
        for field in _INPUT_FIELDS:
            data[field] = getattr(self, field)
        return data


class PerClassMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class ClassificationMetrics(BaseModel):
    n_cases: int
    accuracy: float
    balanced_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_precision: float
    weighted_recall: float
    weighted_f1: float
    per_class: dict[str, PerClassMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    cost_weighted_error: float


class RankingMetrics(BaseModel):
    positive_class: str = "DENY"
    auc_roc: float | None = None
    ks_statistic: float | None = None
    gini: float | None = None


class ReliabilityBin(BaseModel):
    lower: float
    upper: float
    count: int
    avg_confidence: float
    accuracy: float


class CalibrationMetrics(BaseModel):
    brier_score: float | None = None
    expected_calibration_error: float | None = None
    reliability_bins: list[ReliabilityBin] = Field(default_factory=list)


class RuntimeMetrics(BaseModel):
    n_decisions: int = 0
    decision_distribution: dict[str, int] = Field(default_factory=dict)
    suspend_rate: float = 0.0
    auto_decision_rate: float = 0.0
    mean_confidence: float = 0.0
    below_threshold_rate: float = 0.0
    gate_trigger_counts: dict[str, int] = Field(default_factory=dict)
    crew_agreement_rate: float | None = None


class MetricsReport(BaseModel):
    n_cases: int
    classification: ClassificationMetrics
    ranking: RankingMetrics
    calibration: CalibrationMetrics
    runtime: RuntimeMetrics
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
