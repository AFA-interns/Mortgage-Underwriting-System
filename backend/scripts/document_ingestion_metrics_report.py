"""Document Ingestion Agent evaluation report (CLI) - runs the REAL agent
against the bundled mock-document scenarios (known, hand-written ground
truth) and computes metrics from app.document_ingestion.metrics over the
actual outputs. Small (6 bundles, ~27 documents) but real, unlike the
fabricated "40-case benchmark" this replaces - see DOCUMENT_INGESTION_METRICS.md.

Usage (from backend/):
    venv\\Scripts\\python.exe scripts/document_ingestion_metrics_report.py
    venv\\Scripts\\python.exe scripts/document_ingestion_metrics_report.py --output report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.document_ingestion.agent import DocumentIngestionAgent  # noqa: E402
from app.document_ingestion.metrics import (  # noqa: E402
    compute_brier_score,
    compute_classification_metrics,
    compute_cost_weighted_error,
    compute_ece,
    compute_exact_match,
    compute_numeric_accuracy,
    compute_operational_metrics,
    compute_reconciliation_metrics,
    compute_token_f1,
)
from tests.mock_data.generate_docs import (  # noqa: E402
    generate_all_mock_scenarios,
    generate_correctable_pan_scenario,
    generate_image_demo_documents,
)

# Hand-labeled ground truth: ("has_contradiction", "expected_hitl") per bundle.
# Matches this project's own scenario design (see generate_docs.py / README.md).
BUNDLE_LABELS = {
    "clean_prime": {"has_contradiction": False, "expected_hitl": False},
    "name_discrepancy": {"has_contradiction": True, "expected_hitl": True},
    "salary_discrepancy": {"has_contradiction": True, "expected_hitl": True},
    "missing_docs": {"has_contradiction": False, "expected_hitl": True},
    "correctable_pan_error": {"has_contradiction": False, "expected_hitl": True},
    "image_upload": {"has_contradiction": False, "expected_hitl": False},
}

# Ground truth: does this bundle's payslip net pay match its bank credits?
# (name_discrepancy / missing_docs have no bank statement to reconcile
# against at all, so they're intentionally absent here - skipped below.)
SALARY_RECONCILES = {
    "clean_prime": True,
    "salary_discrepancy": False,
    "correctable_pan_error": True,
    "image_upload": True,
}

# Filename substring -> ground-truth document type (matches generate_docs.py's
# own naming convention). Checked in order; first match wins.
_TYPE_PATTERNS = [
    ("bank_statement", "BANK_STATEMENT"),
    ("salary_slip", "SALARY_SLIP"),
    ("form_16", "FORM_16"),
    ("pan_card", "PAN_CARD"),
    ("pan_", "PAN_CARD"),
    ("aadhaar", "AADHAAR_CARD"),
    ("property_sale_deed", "PROPERTY_DEED"),
]


def _expected_type(filename: str) -> str:
    name = filename.lower()
    for pattern, doc_type in _TYPE_PATTERNS:
        if pattern in name:
            return doc_type
    return "UNKNOWN"


def _load_bundles() -> dict[str, list[str]]:
    bundles = dict(generate_all_mock_scenarios())
    bundles["correctable_pan_error"] = generate_correctable_pan_scenario()
    bundles["image_upload"] = generate_image_demo_documents()
    return bundles


def run_report() -> dict:
    bundles = _load_bundles()

    y_true_types: list[str] = []
    y_pred_types: list[str] = []
    confidences: list[float] = []
    correctness: list[int] = []
    recon_eval_cases: list[dict] = []
    audit_records: list[dict] = []
    per_bundle: list[dict] = []

    for name, paths in bundles.items():
        label = BUNDLE_LABELS[name]
        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=paths, application_id=f"BENCH-{name.upper()}",
        )

        for meta in output.documents_metadata:
            y_true_types.append(_expected_type(meta.original_filename))
            y_pred_types.append(str(meta.classified_type.value))

        conf = output.confidence.overall_confidence
        predicted_hitl = output.human_review.requires_human_review
        is_correct = 1 if predicted_hitl == label["expected_hitl"] else 0
        confidences.append(conf)
        correctness.append(is_correct)

        name_matches = output.reconciliation.name_matches
        if name == "name_discrepancy":
            # Ground truth: this bundle's documents carry different name
            # spellings - the agent should flag at least one pair as a mismatch.
            name_match_correct = any(not m.is_match for m in name_matches) if name_matches else False
        else:
            # Ground truth: one consistent name everywhere - no pair should
            # be flagged as a mismatch.
            name_match_correct = all(m.is_match for m in name_matches) if name_matches else True

        recon_case = {
            "has_contradiction": label["has_contradiction"],
            "predicted_has_contradiction": output.reconciliation.total_contradictions_count > 0,
            "name_match_correct": name_match_correct,
        }
        if name in SALARY_RECONCILES:
            salary_recons = output.reconciliation.salary_reconciliations
            predicted_reconciles = all(r.is_reconciled for r in salary_recons) if salary_recons else None
            if predicted_reconciles is not None:
                recon_case["salary_reconcile_correct"] = predicted_reconciles == SALARY_RECONCILES[name]
        recon_eval_cases.append(recon_case)

        audit_records.append({
            "requires_human_review": predicted_hitl,
            "overall_confidence": conf,
            "reasons": output.human_review.reasons,
        })

        per_bundle.append({
            "bundle": name,
            "documents": len(paths),
            "overall_confidence": conf,
            "confidence_level": output.confidence.confidence_level,
            "requires_human_review": predicted_hitl,
            "expected_hitl": label["expected_hitl"],
            "hitl_decision_correct": bool(is_correct),
            "contradictions_detected": output.reconciliation.total_contradictions_count,
            "missing_mandatory_documents": output.checklist.missing_mandatory_documents,
        })

    report: dict = {
        "sample_size": {
            "bundles": len(bundles),
            "documents": len(y_true_types),
        },
        "classification": compute_classification_metrics(y_true_types, y_pred_types),
        "cost_weighted_error": compute_cost_weighted_error(y_true_types, y_pred_types),
        "calibration": {
            "brier_score": compute_brier_score(confidences, correctness),
            **dict(zip(("ece", "reliability_bins"), compute_ece(confidences, correctness, num_bins=5))),
        },
        "reconciliation": compute_reconciliation_metrics(recon_eval_cases),
        "operational": compute_operational_metrics(audit_records),
        "per_bundle": per_bundle,
    }

    # Field-level extraction checks on the one bundle with fully known,
    # unambiguous ground-truth field values (clean_prime).
    clean_output = DocumentIngestionAgent.process_document_bundle(
        file_paths=bundles["clean_prime"], application_id="BENCH-FIELD-CHECK",
    )
    pan = clean_output.pan_card
    field_checks = {
        "pan_number_exact_match": compute_exact_match("ABCPS1234F", pan.pan_number if pan else None),
        "borrower_name_token_f1": compute_token_f1(
            "Aarav Sharma", pan.full_name if pan else None
        ),
        "gross_salary_numeric_match": compute_numeric_accuracy(
            150000.0, clean_output.salary_slips[0].gross_salary if clean_output.salary_slips else 0, tolerance=1.0
        ),
        "bank_amb_numeric_match": compute_numeric_accuracy(
            185000.0,
            clean_output.bank_statement.average_monthly_balance if clean_output.bank_statement else 0,
            tolerance=1.0,
        ),
    }
    report["field_level_checks_clean_prime"] = field_checks

    return report


def _print_summary(report: dict) -> None:
    cls = report["classification"]
    cal = report["calibration"]
    recon = report["reconciliation"]
    ops = report["operational"]
    print(f"Sample: {report['sample_size']['bundles']} bundles, {report['sample_size']['documents']} documents"
          " (real agent runs, not fabricated)")
    print(f"Classification accuracy:      {cls['accuracy']:.4f}")
    print(f"Balanced accuracy:            {cls['balanced_accuracy']:.4f}")
    print(f"Cost-weighted error:          {report['cost_weighted_error']:.4f}")
    print(f"Brier score:                  {cal['brier_score']:.4f}")
    print(f"ECE:                          {cal['ece']:.4f}")
    print(f"Contradiction recall:         {recon['contradiction_recall']:.4f}")
    print(f"Contradiction precision:      {recon['contradiction_precision']:.4f}")
    print(f"STP rate:                     {ops.get('straight_through_processing_rate', 0):.4f}")
    print(f"HITL escalation rate:         {ops.get('hitl_escalation_rate', 0):.4f}")
    print("Field-level checks (clean_prime):")
    for k, v in report["field_level_checks_clean_prime"].items():
        print(f"  {k}: {v}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write the full report JSON to this path")
    args = parser.parse_args()

    report = run_report()
    _print_summary(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
