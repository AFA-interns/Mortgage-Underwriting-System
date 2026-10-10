"""Hand-computed checks for app.document_ingestion.metrics - pure functions,
no agent/pipeline execution involved."""
import pytest

from app.document_ingestion.metrics import (
    compute_brier_score,
    compute_cer,
    compute_classification_metrics,
    compute_cost_weighted_error,
    compute_ece,
    compute_exact_match,
    compute_levenshtein_distance,
    compute_numeric_accuracy,
    compute_operational_metrics,
    compute_reconciliation_metrics,
    compute_token_f1,
    compute_wer,
    normalize_text,
)


# --------------------------------------------------------------- OCR text quality

def test_levenshtein_distance_known_values():
    assert compute_levenshtein_distance("kitten", "sitting") == 3
    assert compute_levenshtein_distance("", "abc") == 3
    assert compute_levenshtein_distance("abc", "abc") == 0


def test_cer_known_value():
    # "ABCPS1234F" vs "ABCPS1Z34F": 1 substitution / 10 chars
    assert compute_cer("ABCPS1234F", "ABCPS1Z34F") == 0.1
    assert compute_cer("", "") == 0.0
    assert compute_cer("", "x") == 1.0


def test_wer_known_value():
    assert compute_wer("the quick brown fox", "the quick brown fox") == 0.0
    assert compute_wer("the quick brown fox", "the quick red fox") == pytest.approx(0.25)


# ------------------------------------------------------------- field extraction

def test_normalize_text_strips_punctuation_and_case():
    assert normalize_text("Tata Consultancy Services Ltd.") == "tata consultancy services ltd"
    assert normalize_text(None) == ""


def test_exact_match():
    assert compute_exact_match("ABCPS1234F", "abcps1234f") == 1.0
    assert compute_exact_match("ABCPS1234F", "ABCPS9999F") == 0.0


def test_token_f1_partial_overlap():
    # gt: 4 tokens, pred: 4 tokens, 3 common -> P=R=0.75, F1=0.75
    f1 = compute_token_f1("Tata Consultancy Services Limited", "Tata Consultancy Services Ltd")
    assert f1 == 0.75
    assert compute_token_f1("Aarav Sharma", "Aarav Sharma") == 1.0
    assert compute_token_f1("", "") == 1.0
    assert compute_token_f1("Aarav Sharma", "") == 0.0


def test_numeric_accuracy_tolerance():
    assert compute_numeric_accuracy(150000, 150000.5, tolerance=1.0) == 1.0
    assert compute_numeric_accuracy(150000, 150002, tolerance=1.0) == 0.0
    assert compute_numeric_accuracy(150000, "not-a-number") == 0.0


# ------------------------------------------------------------- classification

def test_classification_metrics_hand_computed():
    y_true = ["PAN_CARD", "PAN_CARD", "AADHAAR_CARD", "AADHAAR_CARD", "SALARY_SLIP"]
    y_pred = ["PAN_CARD", "AADHAAR_CARD", "AADHAAR_CARD", "AADHAAR_CARD", "SALARY_SLIP"]
    m = compute_classification_metrics(y_true, y_pred)

    assert m["total_samples"] == 5
    assert m["accuracy"] == pytest.approx(4 / 5)
    assert m["per_class"]["PAN_CARD"]["recall"] == 0.5
    assert m["per_class"]["AADHAAR_CARD"]["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["per_class"]["SALARY_SLIP"]["f1"] == 1.0


def test_classification_metrics_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        compute_classification_metrics(["PAN_CARD"], [])


def test_cost_weighted_error_penalizes_bank_statement_misclassification_most():
    # Misreading a bank statement as a salary slip (cost 10) must cost far
    # more than misreading a PAN as Aadhaar (cost 4).
    high_cost = compute_cost_weighted_error(["BANK_STATEMENT"], ["SALARY_SLIP"])
    low_cost = compute_cost_weighted_error(["PAN_CARD"], ["AADHAAR_CARD"])
    assert high_cost == 10.0
    assert low_cost == 4.0
    assert compute_cost_weighted_error(["PAN_CARD"], ["PAN_CARD"]) == 0.0


# ------------------------------------------------------------- calibration

def test_brier_score_known_values():
    assert compute_brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert compute_brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_brier_score_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        compute_brier_score([0.5], [])


def test_ece_perfect_calibration_is_zero():
    # Every item at 0.9 confidence, 90% of them correct -> no calibration gap.
    confidences = [0.9] * 10
    correctness = [1] * 9 + [0]
    ece, bins = compute_ece(confidences, correctness, num_bins=5)
    assert ece == 0.0
    assert sum(b["count"] for b in bins) == 10


# ------------------------------------------------------------- reconciliation

def test_reconciliation_metrics_recall_and_precision():
    cases = [
        {"has_contradiction": True, "predicted_has_contradiction": True, "name_match_correct": True},
        {"has_contradiction": True, "predicted_has_contradiction": False, "name_match_correct": False},
        {"has_contradiction": False, "predicted_has_contradiction": True, "name_match_correct": True},
        {"has_contradiction": False, "predicted_has_contradiction": False, "name_match_correct": True},
    ]
    m = compute_reconciliation_metrics(cases)
    assert m["total_actual_contradictions"] == 2
    assert m["detected_contradictions"] == 1
    assert m["contradiction_recall"] == 0.5
    assert m["contradiction_precision"] == 0.5
    assert m["name_matching_accuracy"] == 0.75


# ------------------------------------------------------------- operational

def test_operational_metrics_rates_and_gate_triggers():
    records = [
        {"requires_human_review": False, "overall_confidence": 0.95, "reasons": []},
        {"requires_human_review": True, "overall_confidence": 0.60, "reasons": ["Missing mandatory documents: Aadhaar"]},
        {"requires_human_review": True, "overall_confidence": 0.70, "reasons": ["Name mismatch detected"]},
    ]
    m = compute_operational_metrics(records)
    assert m["total_applications"] == 3
    assert m["hitl_escalation_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["straight_through_processing_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert m["below_threshold_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["safety_gate_triggers"]["missing_mandatory_docs"] == 1
    assert m["safety_gate_triggers"]["name_contradiction"] == 1


def test_operational_metrics_empty_is_empty_dict():
    assert compute_operational_metrics([]) == {}
