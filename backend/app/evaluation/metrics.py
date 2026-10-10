"""Pure-Python evaluation metrics — classification, ranking, and calibration.

Implemented without external ML libraries to keep dependencies minimal.
"""
from __future__ import annotations

from app.evaluation.schemas import (
    CalibrationMetrics,
    ClassificationMetrics,
    PerClassMetrics,
    RankingMetrics,
    ReliabilityBin,
)

DEFAULT_LABELS: list[str] = ["APPROVE", "DENY", "SUSPEND"]

# Cost of predicting column when the truth is row. False-approves are far costlier
# than false-denies in lending.
DEFAULT_COST_MATRIX: dict[str, dict[str, float]] = {
    "APPROVE": {"APPROVE": 0.0, "DENY": 2.0, "SUSPEND": 1.0},
    "DENY": {"APPROVE": 10.0, "DENY": 0.0, "SUSPEND": 2.0},
    "SUSPEND": {"APPROVE": 5.0, "DENY": 1.0, "SUSPEND": 0.0},
}


def confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """Confusion matrix keyed [actual][predicted]."""
    labels = labels or DEFAULT_LABELS
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred, strict=True):
        matrix.setdefault(t, {p: 0 for p in labels})
        matrix[t][p] = matrix[t].get(p, 0) + 1
    return matrix


def _safe_div(numer: float, denom: float) -> float:
    return numer / denom if denom else 0.0


def classification_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
    cost_matrix: dict[str, dict[str, float]] | None = None,
) -> ClassificationMetrics:
    """Accuracy, per-class precision/recall/F1, macro/weighted averages, cost-weighted error."""
    labels = labels or DEFAULT_LABELS
    cost_matrix = cost_matrix or DEFAULT_COST_MATRIX
    n = len(y_true)
    if n == 0:
        raise ValueError("Cannot compute classification metrics on an empty dataset")

    matrix = confusion_matrix(y_true, y_pred, labels)
    correct = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)
    accuracy = correct / n

    per_class: dict[str, PerClassMetrics] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    supports: list[int] = []
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in labels if other != label)
        fn = sum(matrix[label][other] for other in labels if other != label)
        support = tp + fn
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        per_class[label] = PerClassMetrics(
            precision=round(precision, 6),
            recall=round(recall, 6),
            f1=round(f1, 6),
            support=support,
        )
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        supports.append(support)

    macro_precision = sum(precisions) / len(labels)
    macro_recall = sum(recalls) / len(labels)
    macro_f1 = sum(f1s) / len(labels)
    weighted_precision = sum(p * s for p, s in zip(precisions, supports, strict=True)) / n
    weighted_recall = sum(r * s for r, s in zip(recalls, supports, strict=True)) / n
    weighted_f1 = sum(f * s for f, s in zip(f1s, supports, strict=True)) / n
    balanced_accuracy = macro_recall

    total_cost = 0.0
    for t, p in zip(y_true, y_pred, strict=True):
        total_cost += cost_matrix.get(t, {}).get(p, 1.0)
    cost_weighted_error = total_cost / n

    return ClassificationMetrics(
        n_cases=n,
        accuracy=round(accuracy, 6),
        balanced_accuracy=round(balanced_accuracy, 6),
        macro_precision=round(macro_precision, 6),
        macro_recall=round(macro_recall, 6),
        macro_f1=round(macro_f1, 6),
        weighted_precision=round(weighted_precision, 6),
        weighted_recall=round(weighted_recall, 6),
        weighted_f1=round(weighted_f1, 6),
        per_class=per_class,
        confusion_matrix=matrix,
        cost_weighted_error=round(cost_weighted_error, 6),
    )


def _average_ranks(scores: list[float]) -> list[float]:
    """Ranks (1-based) with average ranks for ties."""
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def auc_roc(
    y_binary: list[int],
    scores: list[float],
    invert: bool = False,
) -> float | None:
    """ROC AUC via the Mann-Whitney U statistic (tie-aware). None if a class is missing.

    Set invert=True when lower raw scores indicate a higher chance of the positive
    class (this system's risk_score is a safety score: higher = safer, so DENY
    cases score lower).
    """
    n_pos = sum(y_binary)
    n_neg = len(y_binary) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    if invert:
        scores = [-s for s in scores]
    ranks = _average_ranks(scores)
    rank_sum_pos = sum(r for r, y in zip(ranks, y_binary, strict=True) if y == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def ks_statistic(
    y_binary: list[int],
    scores: list[float],
    invert: bool = False,
) -> float | None:
    """Kolmogorov-Smirnov statistic — max separation between good/bad cumulative rates."""
    n_pos = sum(y_binary)
    n_neg = len(y_binary) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    if invert:
        scores = [-s for s in scores]
    pairs = sorted(zip(scores, y_binary, strict=True), key=lambda x: x[0], reverse=True)
    cum_pos = 0
    cum_neg = 0
    ks = 0.0
    for _, y in pairs:
        if y == 1:
            cum_pos += 1
        else:
            cum_neg += 1
        ks = max(ks, abs(cum_pos / n_pos - cum_neg / n_neg))
    return round(ks, 6)


def brier_score(confidences: list[float], correct: list[int]) -> float:
    """Mean squared error of confidence vs actual correctness (0 = perfectly calibrated)."""
    if not confidences:
        raise ValueError("Cannot compute Brier score on an empty dataset")
    return sum((c - y) ** 2 for c, y in zip(confidences, correct, strict=True)) / len(
        confidences
    )


def reliability_bins(
    confidences: list[float],
    correct: list[int],
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Confidence-binned reliability table (only non-empty bins)."""
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for c, y in zip(confidences, correct, strict=True):
        idx = min(int(c * n_bins), n_bins - 1)
        buckets[idx].append((c, y))
    bins: list[ReliabilityBin] = []
    for idx, bucket in enumerate(buckets):
        if not bucket:
            continue
        lower = idx / n_bins
        upper = (idx + 1) / n_bins
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(y for _, y in bucket) / len(bucket)
        bins.append(
            ReliabilityBin(
                lower=round(lower, 4),
                upper=round(upper, 4),
                count=len(bucket),
                avg_confidence=round(avg_conf, 6),
                accuracy=round(acc, 6),
            )
        )
    return bins


def expected_calibration_error(
    confidences: list[float],
    correct: list[int],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error — confidence-weighted gap between confidence and accuracy."""
    if not confidences:
        raise ValueError("Cannot compute ECE on an empty dataset")
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for c, y in zip(confidences, correct, strict=True):
        idx = min(int(c * n_bins), n_bins - 1)
        buckets[idx].append((c, y))
    n = len(confidences)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(y for _, y in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(avg_conf - acc)
    return round(ece, 6)


def ranking_metrics(
    y_binary: list[int],
    scores: list[float],
    invert: bool = False,
) -> RankingMetrics:
    """AUC-ROC, KS, and Gini from a binary label and a continuous score."""
    auc = auc_roc(y_binary, scores, invert=invert)
    ks = ks_statistic(y_binary, scores, invert=invert)
    return RankingMetrics(
        positive_class="DENY",
        auc_roc=round(auc, 6) if auc is not None else None,
        ks_statistic=ks,
        gini=round(2 * auc - 1, 6) if auc is not None else None,
    )


def calibration_metrics(
    confidences: list[float],
    correct: list[int],
    n_bins: int = 10,
) -> CalibrationMetrics:
    """Brier score, ECE, and reliability bins for predicted confidence vs correctness."""
    if not confidences:
        return CalibrationMetrics()
    return CalibrationMetrics(
        brier_score=round(brier_score(confidences, correct), 6),
        expected_calibration_error=expected_calibration_error(
            confidences, correct, n_bins=n_bins
        ),
        reliability_bins=reliability_bins(confidences, correct, n_bins=n_bins),
    )
