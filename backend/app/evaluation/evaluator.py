"""Decision Agent evaluation — offline metrics over labeled cases + runtime metrics."""
from __future__ import annotations

from app.evaluation.metrics import (
    calibration_metrics,
    classification_metrics,
    ranking_metrics,
)
from app.evaluation.schemas import LabeledCase, MetricsReport, RuntimeMetrics
from app.models.decision import DecisionResult

DEFAULT_CONFIDENCE_THRESHOLD = 0.85


def evaluate_cases(
    cases: list[LabeledCase],
    predictions: dict[str, DecisionResult] | None = None,
) -> MetricsReport:
    """Compute the full metrics report for labeled cases.

    Predictions resolve per case as: case.predicted first, then the
    ``predictions`` dict keyed by application_id. At least one must exist.
    """
    if not cases:
        raise ValueError("Cannot evaluate an empty case list")
    predictions = predictions or {}

    y_true: list[str] = []
    y_pred: list[str] = []
    confidences: list[float] = []
    risk_scores: list[float] = []
    decisions: list[DecisionResult] = []

    for case in cases:
        prediction = case.predicted or predictions.get(case.application_id)
        if prediction is None:
            raise ValueError(
                f"No prediction available for application_id={case.application_id!r}; "
                "provide LabeledCase.predicted or a predictions mapping"
            )
        y_true.append(case.ground_truth_decision.value)
        y_pred.append(prediction.decision.value)
        confidences.append(prediction.confidence)
        risk_scores.append(prediction.risk_score)
        decisions.append(prediction)

    classification = classification_metrics(y_true, y_pred)
    # risk_score is a safety score (higher = safer) → invert so DENY cases rank high.
    ranking = ranking_metrics(
        [1 if label == "DENY" else 0 for label in y_true],
        risk_scores,
        invert=True,
    )
    calibration = calibration_metrics(
        confidences,
        [1 if t == p else 0 for t, p in zip(y_true, y_pred, strict=True)],
    )
    runtime = runtime_metrics_from_decisions(decisions)

    return MetricsReport(
        n_cases=len(cases),
        classification=classification,
        ranking=ranking,
        calibration=calibration,
        runtime=runtime,
    )


def runtime_metrics_from_decisions(
    decisions: list[DecisionResult],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> RuntimeMetrics:
    """Operational metrics over a set of produced decisions (no labels needed)."""
    n = len(decisions)
    if n == 0:
        return RuntimeMetrics()

    distribution: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    agreement_pairs = 0
    agreement_hits = 0

    for decision in decisions:
        label = decision.decision.value
        distribution[label] = distribution.get(label, 0) + 1
        if decision.gate_triggered:
            gate_counts[decision.gate_triggered] = gate_counts.get(decision.gate_triggered, 0) + 1

        consensus = decision.agent_consensus or {}
        underwriter = (consensus.get("underwriter") or {}).get("recommendation")
        analyst = (consensus.get("risk_analyst") or {}).get("recommendation")
        if underwriter and analyst:
            agreement_pairs += 1
            if underwriter == analyst:
                agreement_hits += 1

    suspend_rate = distribution.get("SUSPEND", 0) / n
    mean_confidence = sum(d.confidence for d in decisions) / n
    below_threshold = sum(1 for d in decisions if d.confidence < confidence_threshold) / n

    return RuntimeMetrics(
        n_decisions=n,
        decision_distribution=distribution,
        suspend_rate=round(suspend_rate, 6),
        auto_decision_rate=round(1.0 - suspend_rate, 6),
        mean_confidence=round(mean_confidence, 6),
        below_threshold_rate=round(below_threshold, 6),
        gate_trigger_counts=dict(sorted(gate_counts.items())),
        crew_agreement_rate=(
            round(agreement_hits / agreement_pairs, 6) if agreement_pairs else None
        ),
    )
