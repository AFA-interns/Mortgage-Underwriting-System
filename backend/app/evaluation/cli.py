"""CLI — evaluate the Decision Agent over a labeled dataset.

Usage (from backend/):
    python -m app.evaluation.cli --dataset data/labeled_cases.json --use-pipeline
    python -m app.evaluation.cli --dataset data/labeled_cases.json --predictions preds.json
    Add --output report.json to write the full MetricsReport JSON to a file.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.evaluation.evaluator import evaluate_cases
from app.evaluation.loader import load_labeled_cases, load_predictions
from app.evaluation.runner import run_deterministic_pipeline
from app.evaluation.schemas import MetricsReport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute evaluation metrics for the Decision Agent."
    )
    parser.add_argument("--dataset", required=True, help="Path to labeled cases JSON")
    parser.add_argument(
        "--predictions",
        help="Path to precomputed predictions JSON (alternative to --use-pipeline)",
    )
    parser.add_argument(
        "--use-pipeline",
        action="store_true",
        help="Run the deterministic (no-LLM) pipeline over each case to produce predictions",
    )
    parser.add_argument("--output", help="Write the full MetricsReport JSON to this path")
    return parser


def _summary(report: MetricsReport) -> str:
    c = report.classification
    lines = [
        f"Cases evaluated:        {report.n_cases}",
        f"Accuracy:               {c.accuracy:.4f}",
        f"Balanced accuracy:      {c.balanced_accuracy:.4f}",
        f"Macro F1:               {c.macro_f1:.4f}",
        f"Cost-weighted error:    {c.cost_weighted_error:.4f}",
        f"AUC-ROC (DENY):         {report.ranking.auc_roc}",
        f"KS statistic:           {report.ranking.ks_statistic}",
        f"Gini:                   {report.ranking.gini}",
        f"Brier score:            {report.calibration.brier_score}",
        f"ECE:                    {report.calibration.expected_calibration_error}",
        f"Suspend rate:           {report.runtime.suspend_rate:.4f}",
        f"Crew agreement rate:    {report.runtime.crew_agreement_rate}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_labeled_cases(args.dataset)
        predictions = None
        if args.use_pipeline and args.predictions:
            raise ValueError("--use-pipeline and --predictions are mutually exclusive")
        if args.use_pipeline:
            for case in cases:
                case.predicted = run_deterministic_pipeline(case.as_pipeline_input())
        elif args.predictions:
            predictions = load_predictions(args.predictions)
        report = evaluate_cases(cases, predictions=predictions)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(_summary(report))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nFull report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
