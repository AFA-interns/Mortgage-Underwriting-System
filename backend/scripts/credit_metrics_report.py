"""Credit Agent evaluation report (CLI). Reads an exported JSON/JSONL file; it
never connects to the database.

    cd backend
    python scripts/credit_metrics_report.py --input applications.jsonl
    python scripts/credit_metrics_report.py --input applications.jsonl --baseline baseline.json
    python scripts/credit_metrics_report.py --input applications.jsonl --save-baseline baseline.json

Writes metrics_report.json and metrics_report.md to --out-dir (default ./metrics_out).

Export the input from PostgreSQL (psql, one JSON object per line). Table/column
names are from app/services/db.py: `applications.view` is the JSONB document
holding the whole application (view->'agents'->'credit' is credit_analysis,
view->'agents'->'decision' the Decision Agent output); reviewer corrections live
in `documents.field_overrides`; gender is NOT in the view - it is only in the
Aadhaar document's `documents.parsed_fields->'fields'->>'gender'`. There is no
outcome column yet (see CREDIT_METRICS.md, "What to start capturing"), so
`outcome_bad` is exported as NULL.

    \\t on
    \\pset format unaligned
    \\o applications.jsonl
    SELECT json_build_object(
        'id',              a.id,
        'created_at',      a.created_at,
        'view',            a.view,
        'gender',          (SELECT d.parsed_fields->'fields'->>'gender'
                              FROM documents d
                             WHERE d.application_id = a.id AND d.doc_type = 'AADHAAR_CARD'
                             LIMIT 1),
        -- {} = has reviewable documents, nothing corrected; NULL = no documents at all
        'field_overrides', (SELECT jsonb_object_agg(d.id, COALESCE(d.field_overrides, '{}'::jsonb))
                              FROM documents d
                             WHERE d.application_id = a.id AND d.parsed_fields IS NOT NULL),
        'outcome_bad',     NULL
    )
    FROM applications a
    ORDER BY a.created_at;
    \\o

(Applications with no parsed documents come out with field_overrides = null and
are counted as "not reviewed".)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.credit import metrics as m  # noqa: E402


def load_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if text[0] == "[":
        return json.loads(text)
    if text[0] == "{" and "\n" not in text:
        return [json.loads(text)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return out + [""]


def render_markdown(report: dict[str, Any]) -> str:
    p1 = report["phase1"]
    mix = p1["bureau_source_mix"]
    lines = ["# Bureau data source mix (read this first)", ""]
    if mix["sources"]["simulated"]["count"] > 0:
        lines += [
            f"> **WARNING: {mix['simulated_share_pct']}% of these applications used SIMULATED bureau data.** "
            "Simulated scores are derived from the application id, not the borrower, so every figure "
            "below is a statement about the stub, not about real credit risk.",
            "",
        ]
    elif mix["total"] == 0:
        lines += ["> No applications in the input.", ""]
    if mix["unverified_share_pct"] > 0 and mix["sources"]["simulated"]["count"] == 0:
        lines += [f"> Note: {mix['unverified_share_pct']}% of applications used unverified bureau data "
                  "(declared score or demo fixture).", ""]
    lines += _table(["Source", "Count", "%"], [[k, v["count"], v["pct"]] for k, v in mix["sources"].items()])
    lines += [f"Total: {mix['total']} | Meets production target (0% simulated): "
              f"**{mix['meets_production_target']}**", ""]

    lines += ["# Credit Agent metrics report", "", f"Applications: {p1['n_applications']}", ""]
    if report.get("synthetic_label"):
        lines += [f"> {report['synthetic_label']}", ""]

    fr = p1["flag_trigger_rates"]
    lines += ["## Red-flag trigger rates", ""]
    lines += _table(["Flag", "Count", "%"], [[k, v["count"], v["pct"]] for k, v in fr["flags"].items()])

    dd = p1["decision_distribution"]
    lines += ["## Credit decision distribution", ""]
    lines += _table(["Decision", "Count", "%"], [[k, v["count"], v["pct"]] for k, v in dd["decisions"].items()])

    cd = p1["confidence_distribution"]
    lines += ["## Confidence", "",
              f"At the {cd['formula']['floor']} floor: {cd['at_floor_count']} ({cd['at_floor_pct']}%)"
              + (" - **ALERT: more than 20% at the floor**" if cd["floor_alert"] else ""),
              f"Formula mismatches: {len(cd['formula_mismatches'])}"
              + (f" ({', '.join(str(x['application_id']) for x in cd['formula_mismatches'][:20])})"
                 if cd["formula_mismatches"] else ""), ""]
    lines += _table(["Bin", "Count", "%"], [[b["bin"], b["count"], b["pct"]] for b in cd["histogram"] if b["count"]])

    am = p1["agreement_matrix"]
    lines += ["## Credit Agent vs Decision Agent", "",
              f"Agreement: {am['agreement_rate_pct']}% of {am['compared']} compared ({am['skipped']} skipped). "
              f"Severe conflicts: **{len(am['severe_conflicts'])}**", ""]
    lines += _table(["Credit \\ Decision", *am["cols"]],
                    [[r, *[am["matrix"][r][c] for c in am["cols"]]] for r in am["rows"]])
    if am["severe_conflicts"]:
        lines += ["Severe conflicts: " + ", ".join(
            f"{c['application_id']} ({c['credit']} vs {c['decision']})" for c in am["severe_conflicts"]), ""]

    uq = p1["upstream_data_quality_rate"]
    lines += ["## Upstream data quality", "",
              f"Reviewed: {uq['reviewed']} | with an income/debt override: {uq['overridden']} "
              f"(**{uq['rate_pct']}%**) | not reviewed: {uq['not_reviewed']}", ""]

    air = p1["adverse_impact_ratio"]
    lines += [f"## Adverse impact ratio ({air['group_key']})", ""]
    for label, key in (("APPROVE", "favourable_approve"), ("APPROVE + CONDITIONAL", "favourable_approve_or_conditional")):
        a = air[key]
        verdict = "n/a" if a["air"] is None else f"{a['air']} ({'BELOW 0.80 - investigate' if a['flagged'] else 'ok'})"
        lines.append(f"- Favourable = {label}: AIR {verdict} [{a['status']}], rates % {a['rates_pct']}")
    lines += ["", f"_{air['note']}_", ""]

    lines += ["## Drift (PSI on risk_score)", ""]
    psi = report.get("psi")
    if not psi or not psi.get("available"):
        lines += [f"Not computed: {(psi or {}).get('reason', 'no --baseline given')}.", ""]
    else:
        lines += [f"PSI **{psi['psi']}** - {psi['status']} (baseline n={psi['n_baseline']}, current n={psi['n_current']})", ""]

    lines += ["## Outcome metrics", ""]
    oc = report["outcomes"]
    if not oc["available"]:
        lines += [f"Not available: {oc['reason']}", ""]
    else:
        lines += [f"AUC {oc['auc']} ({oc['auc_status']}), Gini {oc['gini']}, KS {oc['ks']} "
                  f"({oc['ks_status']}, {oc['ks_basis']}); n={oc['n_labelled']}, bad={oc['n_bad']}", ""]
        lines += [f"- {w}" for w in oc["warnings"]]
        for key in ("bad_rate_by_credit_band", "bad_rate_by_credit_risk_tier"):
            br = oc[key]
            lines += ["", f"Bad rate by {br['field']} (monotonic: **{br['monotonic']}**)", ""]
            lines += _table(["Group", "n", "bad", "bad rate %"],
                            [[g, s["n"], s["bad"], s["bad_rate_pct"]] for g, s in br["groups"].items()])
        lines += ["", "Confidence calibration", ""]
        lines += _table(["Confidence", "n", "mean conf", "realised correct", "well calibrated"],
                        [[b["range"], b["n"], b["mean_confidence"], b["realised_correct"], b["well_calibrated"]]
                         for b in oc["confidence_calibration"]["buckets"]])
    return "\n".join(lines).rstrip() + "\n"


def build_report(
    rows: list[dict[str, Any]],
    group_key: str = "gender",
    baseline: list[float] | None = None,
    psi_bins: int = 10,
    synthetic_label: str | None = None,
) -> dict[str, Any]:
    records = m.normalize_records(rows)
    current = [float(r["credit_analysis"]["risk_score"]) for r in records
               if (r.get("credit_analysis") or {}).get("risk_score") is not None]
    psi = None
    if baseline:
        psi = m.psi(baseline, current, m.quantile_edges(baseline, psi_bins))
    return {
        "synthetic_label": synthetic_label,
        "phase1": m.phase1_report(records, group_key=group_key),
        "psi": psi,
        "outcomes": m.outcome_report(records),
        "_risk_scores": current,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", required=True, type=Path, help="JSON array or JSONL of exported application rows")
    ap.add_argument("--baseline", type=Path, help="JSON list of baseline risk scores (enables PSI)")
    ap.add_argument("--save-baseline", type=Path, help="write this batch's risk scores as a baseline file")
    ap.add_argument("--out-dir", type=Path, default=Path("./metrics_out"))
    ap.add_argument("--group-key", default="gender", help="audit attribute for adverse impact ratio")
    ap.add_argument("--psi-bins", type=int, default=10)
    ap.add_argument("--label", help="banner shown in the report, e.g. 'SYNTHETIC DATA'")
    args = ap.parse_args(argv)

    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    report = build_report(load_rows(args.input), args.group_key, baseline, args.psi_bins, args.label)

    if args.save_baseline:
        args.save_baseline.write_text(json.dumps(report["_risk_scores"]), encoding="utf-8")
    report.pop("_risk_scores")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "metrics_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (args.out_dir / "metrics_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {args.out_dir / 'metrics_report.json'} and {args.out_dir / 'metrics_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
