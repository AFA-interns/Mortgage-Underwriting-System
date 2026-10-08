"""Tests for evaluation metrics, loaders, CLI, endpoints, and labeled dataset."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.evaluation.cli import main as cli_main
from app.evaluation.evaluator import evaluate_cases, runtime_metrics_from_decisions
from app.evaluation.loader import load_labeled_cases, load_predictions
from app.evaluation.metrics import (
    auc_roc,
    brier_score,
    classification_metrics,
    confusion_matrix,
    expected_calibration_error,
    ks_statistic,
    reliability_bins,
)
from app.evaluation.runner import run_deterministic_pipeline
from app.evaluation.schemas import LabeledCase
from app.evaluation.synth import build_dataset
from app.main import app
from app.models.decision import DecisionResult, DecisionType
from app.services.audit import audit_store, create_audit_record
from tests.conftest import (
    get_good_case,
    get_missing_inputs_case,
    get_suspend_case,
    get_weak_case,
)

DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "labeled_cases.json"

client = TestClient(app)


@pytest.fixture
def isolated_audit_store():
    saved = list(audit_store._records)
    audit_store._records.clear()
    try:
        yield audit_store
    finally:
        audit_store._records.clear()
        audit_store._records.extend(saved)


def _decision(
    app_id: str,
    decision: DecisionType,
    confidence: float = 0.9,
    risk_score: float = 50.0,
    gate: str | None = None,
    consensus: dict | None = None,
) -> DecisionResult:
    return DecisionResult(
        application_id=app_id,
        decision=decision,
        confidence=confidence,
        risk_score=risk_score,
        gate_triggered=gate,
        agent_consensus=consensus or {},
    )


# ── Classification metrics ─────────────────────────────────────────────────────


def test_confusion_matrix_layout():
    y_true = ["APPROVE", "APPROVE", "DENY", "DENY"]
    y_pred = ["APPROVE", "DENY", "DENY", "DENY"]
    matrix = confusion_matrix(y_true, y_pred)
    assert matrix["APPROVE"]["APPROVE"] == 1
    assert matrix["APPROVE"]["DENY"] == 1
    assert matrix["DENY"]["DENY"] == 2
    assert sum(sum(row.values()) for row in matrix.values()) == 4


def test_classification_metrics_hand_computed():
    y_true = ["APPROVE", "APPROVE", "APPROVE", "DENY", "DENY", "SUSPEND"]
    y_pred = ["APPROVE", "APPROVE", "DENY", "DENY", "APPROVE", "SUSPEND"]
    m = classification_metrics(y_true, y_pred)

    assert m.n_cases == 6
    assert m.accuracy == pytest.approx(0.666667, abs=1e-5)
    assert m.balanced_accuracy == pytest.approx(0.722222, abs=1e-5)

    approve = m.per_class["APPROVE"]
    assert approve.precision == pytest.approx(0.666667, abs=1e-5)
    assert approve.recall == pytest.approx(0.666667, abs=1e-5)
    assert approve.f1 == pytest.approx(0.666667, abs=1e-5)
    assert approve.support == 3

    deny = m.per_class["DENY"]
    assert deny.precision == 0.5
    assert deny.recall == 0.5
    assert deny.f1 == 0.5
    assert deny.support == 2

    suspend = m.per_class["SUSPEND"]
    assert suspend.precision == 1.0
    assert suspend.recall == 1.0
    assert suspend.support == 1

    assert m.macro_precision == pytest.approx(0.722222, abs=1e-5)
    assert m.macro_f1 == pytest.approx(0.722222, abs=1e-5)
    assert m.weighted_f1 == pytest.approx(0.666667, abs=1e-5)
    assert m.macro_precision != m.weighted_precision  # supports differ


def test_cost_weighted_error_asymmetric():
    # False-approve (truth DENY, predicted APPROVE) must cost far more than false-deny.
    y_true = ["DENY", "APPROVE"]
    y_pred = ["APPROVE", "DENY"]
    m = classification_metrics(y_true, y_pred)
    assert m.cost_weighted_error == 6.0  # (10 + 2) / 2


def test_classification_metrics_empty_raises():
    with pytest.raises(ValueError, match="empty dataset"):
        classification_metrics([], [])


# ── Ranking metrics ────────────────────────────────────────────────────────────


def test_auc_perfect_separation_with_invert():
    # risk_score is a safety score: DENY cases score lower.
    y_binary = [1, 0]
    safety_scores = [20.0, 90.0]
    assert auc_roc(y_binary, safety_scores, invert=True) == 1.0
    assert auc_roc(y_binary, safety_scores, invert=False) == 0.0


def test_auc_known_value_with_invert():
    y_binary = [1, 0, 1, 0]
    safety_scores = [30.0, 40.0, 70.0, 50.0]
    # Positive beats negative in 2 of 4 pairs.
    assert auc_roc(y_binary, safety_scores, invert=True) == pytest.approx(0.5)


def test_auc_single_class_returns_none():
    assert auc_roc([1, 1], [30.0, 40.0]) is None
    assert auc_roc([0, 0], [30.0, 40.0]) is None


def test_ks_statistic_perfect_separation():
    y_binary = [1, 1, 0, 0]
    safety_scores = [10.0, 20.0, 80.0, 90.0]
    assert ks_statistic(y_binary, safety_scores, invert=True) == 1.0


def test_ks_statistic_single_class_returns_none():
    assert ks_statistic([1, 1, 1], [10.0, 20.0, 30.0]) is None


def test_ranking_metrics_gini_derived_from_auc():
    from app.evaluation.metrics import ranking_metrics

    report = ranking_metrics([1, 0, 1, 0], [30.0, 40.0, 70.0, 50.0], invert=True)
    assert report.auc_roc == pytest.approx(0.5)
    assert report.gini == pytest.approx(0.0)
    assert report.positive_class == "DENY"


# ── Calibration metrics ────────────────────────────────────────────────────────


def test_brier_score_known_values():
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert brier_score([0.9, 0.4, 0.6], [1, 0, 1]) == pytest.approx(0.11)


def test_ece_perfect_and_imperfect_calibration():
    assert expected_calibration_error([0.5, 0.5, 1.0, 1.0], [0, 1, 1, 1]) == 0.0
    assert expected_calibration_error([1.0, 1.0], [0, 1]) == pytest.approx(0.5)


def test_reliability_bins_skip_empty():
    bins = reliability_bins([0.05, 0.95], [0, 1], n_bins=10)
    assert len(bins) == 2
    assert bins[0].lower == 0.0 and bins[0].upper == 0.1
    assert bins[1].avg_confidence == pytest.approx(0.95)


# ── Loaders ────────────────────────────────────────────────────────────────────


def _minimal_labeled(app_id: str = "T-1") -> dict:
    return {
        "application_id": app_id,
        "borrower_profile": {"name": "Test", "monthly_income": 100000},
        "ground_truth_decision": "APPROVE",
    }


def test_load_labeled_cases_wrapper_key(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [_minimal_labeled()]}), encoding="utf-8")
    cases = load_labeled_cases(path)
    assert len(cases) == 1
    assert cases[0].ground_truth_decision == DecisionType.APPROVE


def test_load_labeled_cases_bare_list(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_minimal_labeled()]), encoding="utf-8")
    assert len(load_labeled_cases(path)) == 1


def test_load_labeled_cases_missing_label_raises(tmp_path):
    bad = {"application_id": "T-2", "borrower_profile": {"name": "X"}}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [_minimal_labeled(), bad]}), encoding="utf-8")
    with pytest.raises(ValueError, match=r"index 1"):
        load_labeled_cases(path)


def test_load_labeled_cases_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_labeled_cases(tmp_path / "nope.json")


def test_load_predictions_keys_by_application_id(tmp_path):
    decision = _decision("T-9", DecisionType.DENY).model_dump(mode="json")
    path = tmp_path / "preds.json"
    path.write_text(json.dumps({"predictions": [decision]}), encoding="utf-8")
    predictions = load_predictions(path)
    assert predictions["T-9"].decision == DecisionType.DENY


# ── Evaluator ──────────────────────────────────────────────────────────────────


def test_evaluate_missing_prediction_raises():
    case = LabeledCase.model_validate(_minimal_labeled())
    with pytest.raises(ValueError, match="No prediction available"):
        evaluate_cases([case])


def test_evaluate_conftest_cases_exact_metrics():
    specs = [
        (get_good_case, DecisionType.APPROVE),
        (get_weak_case, DecisionType.DENY),
        (get_suspend_case, DecisionType.SUSPEND),
        (get_missing_inputs_case, DecisionType.SUSPEND),
    ]
    cases = []
    for case_fn, label in specs:
        pipeline_input = case_fn()
        prediction = run_deterministic_pipeline(pipeline_input)
        normalized = dict(pipeline_input)
        for key in (
            "borrower_profile",
            "document_analysis",
            "credit_analysis",
            "property_analysis",
            "compliance_analysis",
        ):
            normalized[key] = normalized.get(key) or {}
        cases.append(
            LabeledCase.model_validate(
                {
                    **normalized,
                    "ground_truth_decision": label.value,
                    "predicted": prediction,
                }
            )
        )

    report = evaluate_cases(cases)
    assert report.n_cases == 4
    # Pipeline: APPROVE, SUSPEND, SUSPEND, SUSPEND vs labels APPROVE, DENY, SUSPEND, SUSPEND
    assert report.classification.accuracy == 0.75
    assert report.classification.balanced_accuracy == pytest.approx(0.666667, abs=1e-5)
    assert report.classification.per_class["DENY"].recall == 0.0
    assert report.classification.per_class["APPROVE"].f1 == 1.0
    assert report.classification.cost_weighted_error == 0.5  # (DENY→SUSPEND costs 2)/4
    assert report.ranking.auc_roc is not None
    assert 0.0 <= report.ranking.auc_roc <= 1.0
    assert report.calibration.brier_score is not None
    assert report.runtime.n_decisions == 4


def test_evaluate_uses_predictions_mapping():
    case = LabeledCase.model_validate(_minimal_labeled("T-5"))
    predictions = {"T-5": _decision("T-5", DecisionType.APPROVE)}
    report = evaluate_cases([case], predictions=predictions)
    assert report.classification.accuracy == 1.0


def test_shipped_labeled_dataset_evaluates():
    cases = load_labeled_cases(DATASET_PATH)
    assert len(cases) == 32

    labels = [c.ground_truth_decision.value for c in cases]
    assert labels.count("APPROVE") == 11
    assert labels.count("DENY") == 8
    assert labels.count("SUSPEND") == 13

    for case in cases:
        case.predicted = run_deterministic_pipeline(case.as_pipeline_input())
    report = evaluate_cases(cases)

    assert report.n_cases == 32
    assert report.classification.accuracy == 0.875
    assert report.ranking.auc_roc == pytest.approx(0.958333, abs=1e-4)
    assert report.ranking.gini == pytest.approx(0.916667, abs=1e-4)
    assert report.calibration.brier_score is not None
    assert report.runtime.suspend_rate == pytest.approx(0.53125)


def test_synth_build_dataset_labels_independent_of_model():
    cases = build_dataset()
    assert len(cases) == 32
    # LBL-010 is a borderline-strong file labeled APPROVE by design intent,
    # even though the conservative policy suspends it.
    borderline = next(c for c in cases if c.application_id == "LBL-010")
    prediction = run_deterministic_pipeline(borderline.as_pipeline_input())
    assert borderline.ground_truth_decision == DecisionType.APPROVE
    assert prediction.decision == DecisionType.SUSPEND


# ── Runtime metrics ────────────────────────────────────────────────────────────


def test_runtime_metrics_from_decisions():
    decisions = [
        _decision(
            "R-1",
            DecisionType.APPROVE,
            confidence=0.95,
            consensus={
                "underwriter": {"recommendation": "APPROVE"},
                "risk_analyst": {"recommendation": "APPROVE"},
            },
        ),
        _decision(
            "R-2",
            DecisionType.SUSPEND,
            confidence=0.70,
            gate="low_confidence",
            consensus={
                "underwriter": {"recommendation": "APPROVE"},
                "risk_analyst": {"recommendation": "SUSPEND"},
            },
        ),
        _decision("R-3", DecisionType.DENY, confidence=0.90),
    ]
    m = runtime_metrics_from_decisions(decisions, confidence_threshold=0.85)

    assert m.n_decisions == 3
    assert m.decision_distribution == {"APPROVE": 1, "SUSPEND": 1, "DENY": 1}
    assert m.suspend_rate == pytest.approx(1 / 3)
    assert m.auto_decision_rate == pytest.approx(2 / 3)
    assert m.mean_confidence == pytest.approx(0.85)
    assert m.below_threshold_rate == pytest.approx(1 / 3)
    assert m.gate_trigger_counts == {"low_confidence": 1}
    assert m.crew_agreement_rate == 0.5


def test_runtime_metrics_empty():
    m = runtime_metrics_from_decisions([])
    assert m.n_decisions == 0
    assert m.crew_agreement_rate is None


# ── Endpoints ──────────────────────────────────────────────────────────────────


def _labeled_payload(app_id: str = "API-1", with_prediction: bool = True) -> dict:
    case = {
        "application_id": app_id,
        "borrower_profile": {"name": "API Test"},
        "ground_truth_decision": "APPROVE",
    }
    if with_prediction:
        case["predicted"] = _decision(app_id, DecisionType.APPROVE).model_dump(mode="json")
    return {"cases": [case]}


def test_endpoint_evaluation_report_with_predicted():
    response = client.post("/evaluation/report", json=_labeled_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["n_cases"] == 1
    assert body["classification"]["accuracy"] == 1.0
    assert "ranking" in body and "calibration" in body and "runtime" in body


def test_endpoint_evaluation_report_uses_audit_history(isolated_audit_store):
    create_audit_record(
        application_id="API-AUDIT",
        final_decision=_decision("API-AUDIT", DecisionType.DENY),
    )
    response = client.post(
        "/evaluation/report", json=_labeled_payload("API-AUDIT", with_prediction=False)
    )
    assert response.status_code == 200
    body = response.json()
    # Label says APPROVE, audited decision says DENY → 0 accuracy.
    assert body["classification"]["accuracy"] == 0.0


def test_endpoint_evaluation_report_missing_prediction_400(isolated_audit_store):
    response = client.post(
        "/evaluation/report", json=_labeled_payload("API-NOPE", with_prediction=False)
    )
    assert response.status_code == 400
    assert "API-NOPE" in response.json()["detail"]


def test_endpoint_runtime_metrics(isolated_audit_store):
    create_audit_record(
        application_id="RT-1",
        final_decision=_decision(
            "RT-1",
            DecisionType.SUSPEND,
            confidence=0.6,
            gate="missing_inputs",
        ),
    )
    response = client.get("/evaluation/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["n_decisions"] == 1
    assert body["suspend_rate"] == 1.0
    assert body["gate_trigger_counts"] == {"missing_inputs": 1}


def test_endpoint_runtime_empty_store(isolated_audit_store):
    response = client.get("/evaluation/runtime")
    assert response.status_code == 200
    assert response.json()["n_decisions"] == 0


# ── Gate identification ────────────────────────────────────────────────────────


def test_gate_triggered_values():
    cases_and_gates = [
        (get_good_case, None),
        (get_missing_inputs_case, "missing_inputs"),
        (get_suspend_case, "contradiction"),
        (get_weak_case, "contradiction"),
    ]
    for case_fn, expected_gate in cases_and_gates:
        result = run_deterministic_pipeline(case_fn())
        assert result.gate_triggered == expected_gate, case_fn.__name__


def test_gate_triggered_critical_compliance():
    case = get_good_case()
    case["compliance_analysis"]["critical_flags"] = ["FRAUD_ALERT"]
    result = run_deterministic_pipeline(case)
    assert result.decision == DecisionType.SUSPEND
    assert result.gate_triggered == "critical_compliance"


def test_gate_triggered_low_confidence():
    case = get_good_case()
    # Strip evidence and upstream confidence to fall below the 0.85 threshold.
    case["document_analysis"]["provenance"] = []
    case["credit_analysis"]["confidence"] = 0.3
    case["property_analysis"]["valuation_confidence"] = 0.3
    case["compliance_analysis"]["confidence"] = 0.3
    result = run_deterministic_pipeline(case)
    assert result.decision == DecisionType.SUSPEND
    assert result.gate_triggered == "low_confidence"


# ── CLI ────────────────────────────────────────────────────────────────────────


def test_cli_end_to_end(tmp_path):
    output = tmp_path / "report.json"
    exit_code = cli_main(
        ["--dataset", str(DATASET_PATH), "--use-pipeline", "--output", str(output)]
    )
    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_cases"] == 32
    assert payload["classification"]["accuracy"] == 0.875


def test_cli_missing_dataset_returns_error(tmp_path, capsys):
    exit_code = cli_main(["--dataset", str(tmp_path / "missing.json"), "--use-pipeline"])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err
