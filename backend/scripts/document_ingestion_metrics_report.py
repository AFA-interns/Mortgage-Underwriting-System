"""Document Ingestion Agent evaluation report (CLI). Thin wrapper around
app.document_ingestion.benchmark.run_bundled_demo_benchmark() - see that
module for what it actually runs. The same function backs the
/api/v1/metrics/document-ingestion endpoint used by the frontend.

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

from app.document_ingestion.benchmark import run_bundled_demo_benchmark  # noqa: E402


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
    print(f"Gate-passing error rate:      {cal['gate_passing_error_rate']:.4f}")
    print(f"Contradiction recall:         {recon['contradiction_recall']:.4f}")
    print(f"Contradiction precision:      {recon['contradiction_precision']:.4f}")
    print(f"Contradiction handling acc.:  {recon['contradiction_handling_accuracy']:.4f}")
    print(f"STP rate:                     {ops.get('straight_through_processing_rate', 0):.4f}")
    print(f"HITL escalation rate:         {ops.get('hitl_escalation_rate', 0):.4f}")
    print("Field-level checks (clean_prime):")
    for k, v in report["field_level_checks_clean_prime"].items():
        print(f"  {k}: {v}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write the full report JSON to this path")
    args = parser.parse_args()

    report = run_bundled_demo_benchmark()
    _print_summary(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
