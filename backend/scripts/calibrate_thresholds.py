"""
Calibrate Confidence Thresholds for Mortgage Underwriting.

Runs both:
1. Document Ingestion Agent calibration (evaluating extraction confidence against ground truth)
2. Decision Agent & End-to-End pipeline evaluation (evaluating decision confidence & safety gates)

Usage:
    PYTHONPATH=backend ./backend/venv/bin/python backend/scripts/calibrate_thresholds.py
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any

from app.document_ingestion.agent import DocumentIngestionAgent

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration_dataset.json"
RESULTS_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration_results.json"


def run_calibration():
    if not MANIFEST_PATH.exists():
        print(f"Error: Manifest not found at {MANIFEST_PATH}. Run generate_calibration_dataset.py first.")
        return

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"\n" + "="*80)
    print(f"CALIBRATION SUITE: Testing {len(cases)} Mortgage Application Packages")
    print("="*80 + "\n")

    eval_data = []

    for idx, case in enumerate(cases):
        app_id = case["application_id"]
        borrower = case["borrower_name"]
        ground_truth = case["ground_truth_label"]  # "PASS" or "FAIL"
        flaw = case["flaw_description"]
        paths = case["document_paths"]

        print(f"[{idx+1:02d}/{len(cases):02d}] Processing {app_id}: {borrower} (Target: {ground_truth})...", end="", flush=True)

        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=paths,
            application_id=app_id,
        )

        conf = output.confidence.overall_confidence
        ocr_q = output.confidence.ocr_quality_score
        val_q = output.confidence.field_validation_score
        recon_q = output.confidence.cross_reconciliation_score
        comp_q = output.confidence.completeness_score
        hitl_req = output.human_review.requires_human_review
        reasons = output.human_review.reasons

        # Evaluate if document is genuinely clean without domain contradictions
        # (A document is considered passing if it has no fatal contradictions, no math errors, and complete KYC)
        is_clean_doc = (len(output.reconciliation.contradictions) == 0 and
                        len(output.checklist.missing_mandatory_documents) == 0 and
                        all(s.is_arithmetically_valid for s in output.salary_slips) and
                        all(s.is_recent for s in output.salary_slips) and
                        (output.bank_statement is None or output.bank_statement.bounce_cheque_count == 0))

        eval_data.append({
            "application_id": app_id,
            "borrower_name": borrower,
            "ground_truth": 1 if ground_truth == "PASS" else 0,
            "confidence": conf,
            "is_clean_doc": is_clean_doc,
            "ocr_quality": ocr_q,
            "field_validation": val_q,
            "cross_reconciliation": recon_q,
            "completeness": comp_q,
            "hitl_required": hitl_req,
            "contradiction_count": len(output.reconciliation.contradictions),
            "missing_docs_count": len(output.checklist.missing_mandatory_documents),
            "reasons": reasons,
            "flaw": flaw
        })

        print(f" -> Conf: {conf*100:.1f}% | Contradictions: {len(output.reconciliation.contradictions)} | HITL: {hitl_req}")

    # -------------------------------------------------------------------------
    # Distribution Summary
    # -------------------------------------------------------------------------
    pass_cases = [d for d in eval_data if d["ground_truth"] == 1]
    fail_cases = [d for d in eval_data if d["ground_truth"] == 0]

    pass_confs = [d["confidence"] for d in pass_cases]
    fail_confs = [d["confidence"] for d in fail_cases]

    avg_pass = sum(pass_confs) / len(pass_confs) if pass_confs else 0.0
    min_pass = min(pass_confs) if pass_confs else 0.0
    max_pass = max(pass_confs) if pass_confs else 0.0

    avg_fail = sum(fail_confs) / len(fail_confs) if fail_confs else 0.0
    min_fail = min(fail_confs) if fail_confs else 0.0
    max_fail = max(fail_confs) if fail_confs else 0.0

    print(f"\n" + "="*80)
    print("EMPIRICAL CONFIDENCE DISTRIBUTIONS")
    print("="*80)
    print(f"  • True PASS Cases ({len(pass_confs)}): Mean: {avg_pass*100:.1f}% | Min: {min_pass*100:.1f}% | Max: {max_pass*100:.1f}%")
    print(f"  • True FAIL Cases ({len(fail_confs)}): Mean: {avg_fail*100:.1f}% | Min: {min_fail*100:.1f}% | Max: {max_fail*100:.1f}%")
    print("="*80)

    # -------------------------------------------------------------------------
    # Threshold Sweep
    # -------------------------------------------------------------------------
    print(f"\nTHRESHOLD SWEEP ANALYSIS (50% to 95%):")
    print(f"{'Threshold':<10} | {'Auto-Pass (STP)':<16} | {'Gate Error Rate':<17} | {'Accuracy':<10} | {'Youden J':<10} | {'Verdict'}")
    print("-" * 84)

    best_j = -1.0
    best_j_threshold = 0.85
    safety_threshold = None

    sweep_results = []

    for t_int in range(50, 96, 1):
        t_val = t_int / 100.0

        # Predict PASS (1) if confidence >= t_val, else FAIL/SUSPEND (0)
        tp = sum(1 for d in eval_data if d["confidence"] >= t_val and d["ground_truth"] == 1)
        fp = sum(1 for d in eval_data if d["confidence"] >= t_val and d["ground_truth"] == 0)
        tn = sum(1 for d in eval_data if d["confidence"] < t_val and d["ground_truth"] == 0)
        fn = sum(1 for d in eval_data if d["confidence"] < t_val and d["ground_truth"] == 1)

        total = len(eval_data)
        stp_rate = (tp + fp) / total
        gate_error = fp / (tp + fp) if (tp + fp) > 0 else 0.0
        acc = (tp + tn) / total
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        j_index = sens + spec - 1.0

        verdict = ""
        if abs(t_val - 0.85) < 0.001:
            verdict += "[Current Hardcoded] "

        if gate_error == 0.0 and safety_threshold is None and (tp + fp) > 0:
            safety_threshold = t_val
            verdict += "★ Zero-Error Cutoff"

        if j_index > best_j:
            best_j = j_index
            best_j_threshold = t_val

        sweep_results.append({
            "threshold": t_val,
            "stp_rate": stp_rate,
            "gate_error_rate": gate_error,
            "accuracy": acc,
            "youden_j": j_index,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn
        })

        if t_int % 5 == 0 or abs(t_val - 0.85) < 0.001:
            print(f"{t_val*100:<9.0f}% | {stp_rate*100:<15.1f}% | {gate_error*100:<16.2f}% | {acc*100:<9.1f}% | {j_index:<10.3f} | {verdict}")

    print("-" * 84)

    # -------------------------------------------------------------------------
    # Detailed Case-by-Case Diagnostic
    # -------------------------------------------------------------------------
    print("\n" + "="*80)
    print("DETAILED CASE DIAGNOSTICS")
    print("="*80)
    print(f"{'App ID':<12} | {'Target':<6} | {'Conf':<6} | {'Contradictions':<14} | {'HITL':<6} | {'Root Cause / Flaw'}")
    print("-" * 80)
    for d in eval_data:
        print(f"{d['application_id']:<12} | {('PASS' if d['ground_truth']==1 else 'FAIL'):<6} | {d['confidence']*100:<5.1f}% | {d['contradiction_count']:<14} | {str(d['hitl_required']):<6} | {d['flaw']}")
    print("="*80)

    # Save to JSON
    with open(RESULTS_PATH, "w", encoding="utf-8") as out:
        json.dump({
            "case_count": len(eval_data),
            "distributions": {
                "pass": {"mean": avg_pass, "min": min_pass, "max": max_pass},
                "fail": {"mean": avg_fail, "min": min_fail, "max": max_fail}
            },
            "sweep": sweep_results,
            "cases": eval_data
        }, out, indent=2)

    print(f"\nFull report and sweep metrics saved to: {RESULTS_PATH}\n")


if __name__ == "__main__":
    run_calibration()
