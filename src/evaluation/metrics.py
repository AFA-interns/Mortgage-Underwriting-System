"""
Evaluation and Estimation Metrics Suite for Document Ingestion Agent.
Implements:
1. Classification Metrics (Accuracy, Balanced Accuracy, Per-Class Precision/Recall/F1, Cost Matrix)
2. Field-Level Extraction Metrics (Exact Match, Token F1, Numeric Tolerance Accuracy, CER, WER)
3. Validation & Arithmetic Consistency Metrics
4. Cross-Document Reconciliation & Contradiction Detection Recall
5. Confidence Calibration (Brier Score, Expected Calibration Error - ECE, Reliability Bins)
6. Asymmetric Ingestion Cost-Weighted Error
7. Runtime & Operational Metrics (STP Rate, HITL Escalation Rate, Gate Triggers)
"""

import math
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


# -----------------------------------------------------------------------------
# 1. OCR Text Quality Metrics (CER & WER)
# -----------------------------------------------------------------------------

def compute_levenshtein_distance(s1: str, s2: str) -> int:
    """Computes standard Levenshtein edit distance between two strings or token lists."""
    if len(s1) < len(s2):
        return compute_levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def compute_cer(reference_text: str, predicted_text: str) -> float:
    """Character Error Rate: Edit distance / Reference length."""
    if not reference_text:
        return 0.0 if not predicted_text else 1.0
    dist = compute_levenshtein_distance(reference_text, predicted_text)
    return round(min(1.0, dist / max(len(reference_text), 1)), 4)


def compute_wer(reference_text: str, predicted_text: str) -> float:
    """Word Error Rate: Word-level edit distance / Reference word count."""
    ref_words = reference_text.strip().split()
    pred_words = predicted_text.strip().split()
    if not ref_words:
        return 0.0 if not pred_words else 1.0
    dist = compute_levenshtein_distance(ref_words, pred_words)
    return round(min(1.0, dist / max(len(ref_words), 1)), 4)


# -----------------------------------------------------------------------------
# 2. Field-Level Extraction Metrics (Exact Match & Token F1)
# -----------------------------------------------------------------------------

def normalize_text(text: Optional[str]) -> str:
    """Normalizes whitespace, casing, and punctuation for token comparison."""
    if text is None:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def compute_exact_match(ground_truth: Any, prediction: Any) -> float:
    """Returns 1.0 if normalized strings match exactly, else 0.0."""
    gt_norm = normalize_text(ground_truth)
    pred_norm = normalize_text(prediction)
    return 1.0 if gt_norm == pred_norm else 0.0


def compute_token_f1(ground_truth: Any, prediction: Any) -> float:
    """Computes token-level precision, recall, and harmonic mean F1."""
    gt_tokens = normalize_text(ground_truth).split()
    pred_tokens = normalize_text(prediction).split()

    if not gt_tokens and not pred_tokens:
        return 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0

    common_tokens = defaultdict(int)
    for t in pred_tokens:
        if t in gt_tokens:
            common_tokens[t] += 1

    num_same = sum(min(gt_tokens.count(t), pred_tokens.count(t)) for t in set(pred_tokens))
    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(gt_tokens)
    f1 = 2 * (precision * recall) / (precision + recall)
    return round(f1, 4)


def compute_numeric_accuracy(gt_value: float, pred_value: float, tolerance: float = 1.0) -> float:
    """Returns 1.0 if numeric absolute error is within tolerance (e.g., INR 1.00)."""
    try:
        gt_f = float(gt_value)
        pred_f = float(pred_value)
        return 1.0 if abs(gt_f - pred_f) <= tolerance else 0.0
    except (TypeError, ValueError):
        return 0.0


# -----------------------------------------------------------------------------
# 3. Classification Metrics (Accuracy, Precision, Recall, F1, Cost Matrix)
# -----------------------------------------------------------------------------

def compute_classification_metrics(
    y_true: List[str],
    y_pred: List[str],
    classes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Computes comprehensive classification metrics across all document classes."""
    if not y_true or len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be non-empty and of equal length.")

    if classes is None:
        classes = sorted(list(set(y_true + y_pred)))

    n = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = round(correct / n, 4)

    per_class = {}
    recalls = []

    for cls in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp == cls)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != cls and yp == cls)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp != cls)
        support = sum(1 for yt in y_true if yt == cls)

        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 0.0

        per_class[cls] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": support,
        }
        if support > 0:
            recalls.append(rec)

    balanced_accuracy = round(sum(recalls) / len(recalls), 4) if recalls else 0.0

    # Macro averages
    macro_precision = round(sum(d["precision"] for d in per_class.values()) / len(classes), 4)
    macro_recall = round(sum(d["recall"] for d in per_class.values()) / len(classes), 4)
    macro_f1 = round(sum(d["f1"] for d in per_class.values()) / len(classes), 4)

    return {
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "total_samples": n,
    }


# -----------------------------------------------------------------------------
# 4. Asymmetric Ingestion Cost-Weighted Error
# -----------------------------------------------------------------------------

# Ingestion Asymmetric Prototype Cost Matrix
# Misclassifying or failing to extract certain critical items has severe downstream risk
DEFAULT_CLASSIFICATION_COST_MATRIX = {
    # Actual \ Predicted
    "BANK_STATEMENT": {"BANK_STATEMENT": 0, "SALARY_SLIP": 10, "UNKNOWN": 2, "OTHER": 8},
    "PAN_CARD": {"PAN_CARD": 0, "AADHAAR_CARD": 4, "UNKNOWN": 2, "OTHER": 8},
    "AADHAAR_CARD": {"AADHAAR_CARD": 0, "PAN_CARD": 4, "UNKNOWN": 2, "OTHER": 8},
    "SALARY_SLIP": {"SALARY_SLIP": 0, "FORM_16": 3, "UNKNOWN": 2, "OTHER": 6},
    "FORM_16": {"FORM_16": 0, "ITR": 3, "UNKNOWN": 2, "OTHER": 6},
    "PROPERTY_DEED": {"PROPERTY_DEED": 0, "UNKNOWN": 3, "OTHER": 8},
    "UNKNOWN": {"UNKNOWN": 0, "OTHER": 3},
}


def compute_cost_weighted_error(
    y_true: List[str],
    y_pred: List[str],
    cost_matrix: Optional[Dict[str, Dict[str, float]]] = None
) -> float:
    """Computes average cost-weighted penalty across classification predictions."""
    if cost_matrix is None:
        cost_matrix = DEFAULT_CLASSIFICATION_COST_MATRIX

    total_cost = 0.0
    for yt, yp in zip(y_true, y_pred):
        if yt in cost_matrix:
            costs = cost_matrix[yt]
            cost = costs.get(yp, costs.get("OTHER", 5.0))
        else:
            cost = 0.0 if yt == yp else 5.0
        total_cost += cost

    return round(total_cost / max(len(y_true), 1), 4)


# -----------------------------------------------------------------------------
# 5. Confidence Calibration (Brier Score & Expected Calibration Error - ECE)
# -----------------------------------------------------------------------------

def compute_brier_score(confidences: List[float], correctness: List[int]) -> float:
    """
    Brier score = Mean squared error between confidence (0-1) and actual correctness (1 or 0).
    Lower is better (0.0 is perfect calibration).
    """
    if not confidences or len(confidences) != len(correctness):
        raise ValueError("confidences and correctness must be non-empty and of equal length.")

    squared_errors = [(c - y) ** 2 for c, y in zip(confidences, correctness)]
    return round(sum(squared_errors) / len(squared_errors), 4)


def compute_ece(
    confidences: List[float],
    correctness: List[int],
    num_bins: int = 5
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Computes Expected Calibration Error (ECE) and returns diagnostic reliability bins.
    """
    if not confidences or len(confidences) != len(correctness):
        raise ValueError("confidences and correctness must be non-empty and of equal length.")

    bin_size = 1.0 / num_bins
    bins = []
    total_samples = len(confidences)
    ece = 0.0

    for i in range(num_bins):
        bin_lower = i * bin_size
        bin_upper = (i + 1) * bin_size

        # Find items in bin [lower, upper) (or <= upper for last bin)
        bin_items = [
            (c, y) for c, y in zip(confidences, correctness)
            if (bin_lower <= c < bin_upper) or (i == num_bins - 1 and bin_lower <= c <= bin_upper)
        ]

        count = len(bin_items)
        if count > 0:
            avg_conf = sum(c for c, _ in bin_items) / count
            accuracy = sum(y for _, y in bin_items) / count
            ece += (count / total_samples) * abs(avg_conf - accuracy)
        else:
            avg_conf = (bin_lower + bin_upper) / 2.0
            accuracy = 0.0

        bins.append({
            "bin_range": f"{bin_lower:.2f} - {bin_upper:.2f}",
            "count": count,
            "mean_confidence": round(avg_conf, 4),
            "actual_accuracy": round(accuracy, 4),
            "calibration_gap": round(abs(avg_conf - accuracy), 4) if count > 0 else 0.0,
        })

    return round(ece, 4), bins


# -----------------------------------------------------------------------------
# 6. Cross-Document Reconciliation & Contradiction Detection Metrics
# -----------------------------------------------------------------------------

def compute_reconciliation_metrics(
    eval_cases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates contradiction detection and cross-document reconciliation performance:
    - Contradiction Detection Recall (Safety-Critical Recall)
    - Contradiction Detection Precision
    - Name Matching Accuracy
    - Income vs Bank Credit Reconciliation Accuracy
    """
    total_actual_contradictions = 0
    detected_true_contradictions = 0
    false_alarm_contradictions = 0

    name_matches_eval = []
    salary_reconcile_eval = []

    for case in eval_cases:
        actual_has_conflict = case.get("has_contradiction", False)
        pred_has_conflict = case.get("predicted_has_contradiction", False)

        if actual_has_conflict and pred_has_conflict:
            detected_true_contradictions += 1
            total_actual_contradictions += 1
        elif actual_has_conflict and not pred_has_conflict:
            total_actual_contradictions += 1
        elif not actual_has_conflict and pred_has_conflict:
            false_alarm_contradictions += 1

        if "name_match_correct" in case:
            name_matches_eval.append(1 if case["name_match_correct"] else 0)
        if "salary_reconcile_correct" in case:
            salary_reconcile_eval.append(1 if case["salary_reconcile_correct"] else 0)

    contra_recall = round(detected_true_contradictions / max(total_actual_contradictions, 1), 4)
    contra_prec = round(
        detected_true_contradictions / max(detected_true_contradictions + false_alarm_contradictions, 1), 4
    )
    contra_f1 = round(
        2 * contra_prec * contra_recall / max(contra_prec + contra_recall, 1e-6), 4
    )

    name_acc = round(sum(name_matches_eval) / max(len(name_matches_eval), 1), 4)
    salary_acc = round(sum(salary_reconcile_eval) / max(len(salary_reconcile_eval), 1), 4)

    return {
        "contradiction_recall": contra_recall,
        "contradiction_precision": contra_prec,
        "contradiction_f1": contra_f1,
        "name_matching_accuracy": name_acc,
        "salary_reconciliation_accuracy": salary_acc,
        "total_actual_contradictions": total_actual_contradictions,
        "detected_contradictions": detected_true_contradictions,
    }


# -----------------------------------------------------------------------------
# 7. Operational / Runtime Health Metrics
# -----------------------------------------------------------------------------

def compute_operational_metrics(audit_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes runtime service-level metrics from audit trail logs."""
    total_applications = len(audit_records)
    if total_applications == 0:
        return {}

    hitl_count = sum(1 for r in audit_records if r.get("requires_human_review", False))
    stp_count = total_applications - hitl_count
    stp_rate = round(stp_count / total_applications, 4)
    hitl_rate = round(hitl_count / total_applications, 4)

    confidences = [r.get("overall_confidence", 0.0) for r in audit_records]
    mean_conf = round(sum(confidences) / total_applications, 4)
    below_threshold_count = sum(1 for c in confidences if c < 0.85)
    below_threshold_rate = round(below_threshold_count / total_applications, 4)

    gate_counts = defaultdict(int)
    for r in audit_records:
        reasons = r.get("reasons", [])
        for reason in reasons:
            if "Missing mandatory" in reason:
                gate_counts["missing_mandatory_docs"] += 1
            elif "Name mismatch" in reason:
                gate_counts["name_contradiction"] += 1
            elif "Income discrepancy" in reason:
                gate_counts["income_discrepancy"] += 1
            elif "arithmetic inconsistency" in reason:
                gate_counts["salary_arithmetic_failure"] += 1
            elif "below 85%" in reason:
                gate_counts["low_confidence_gate"] += 1
            elif "bounce" in reason:
                gate_counts["banking_bounce_warning"] += 1

    return {
        "total_applications": total_applications,
        "straight_through_processing_rate": stp_rate,
        "hitl_escalation_rate": hitl_rate,
        "mean_confidence": mean_conf,
        "below_threshold_rate": below_threshold_rate,
        "safety_gate_triggers": dict(gate_counts),
    }
