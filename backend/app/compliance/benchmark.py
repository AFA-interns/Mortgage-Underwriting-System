"""Runs the REAL Compliance Agent against this project's own bundled golden
dataset (120 hand-labeled synthetic cases covering KYC, identity, PMLA,
RERA and NHB/PSL checks) and a 60-pair name-matching dataset, and computes
recall/precision/F1 against the hand-written expectations - see
backend/app/compliance/compliance_eval/docs/metrics_spec.csv. Deterministic
rule engine, no LLM involved, so this needs no stored applications unlike
the credit/property/decision metrics.

Mirrors compliance_eval/run_golden.py and run_names.py but returns a JSON
report instead of printing. Shared by the /api/v1/metrics/compliance
endpoint (frontend "run metrics" button).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

import app.graph.nodes.compliance as node_mod
from app.compliance.config import get_compliance_config
from app.compliance.identity_consistency import _names_match
from app.compliance.rules_engine import run_all_checks
from app.models.decision import ComplianceAnalysisResult, Severity

_EVAL_DIR = Path(__file__).resolve().parent / "compliance_eval"
_GOLDEN_CSV = _EVAL_DIR / "data" / "golden.csv"
_NAMES_CSV = _EVAL_DIR / "data" / "names.csv"


def _none_if_empty(v: str) -> str | None:
    return None if v == "" else v


def _golden_row_to_state(r: Any) -> dict[str, Any]:
    raw = json.loads(r.raw_fields)
    docs = json.loads(r.kyc_documents) if r.kyc_documents else []
    return {
        "application_id": r.application_id,
        "borrower_profile": {
            **raw,
            "loan_amount": int(r.loan_amount_inr),
            "property_city_tier": _none_if_empty(r.property_city_tier),
        },
        "document_analysis": {
            "kyc": {
                "documents": docs,
                "pmla": {
                    "source_of_funds_declared": r.pmla_source_of_funds_declared is True
                    or str(r.pmla_source_of_funds_declared) == "True",
                    "identity_verification_logged": str(r.pmla_identity_verification_log_present) == "True",
                },
            },
            "borrower_identity": {
                "application_form_name": _none_if_empty(r.application_name),
                "application_form_dob": _none_if_empty(r.application_dob),
                "application_form_pan_number": _none_if_empty(r.application_pan),
                "pan_card_name": _none_if_empty(r.pan_name),
                "pan_card_number": _none_if_empty(r.pan_card_number),
                "aadhaar_name": _none_if_empty(r.aadhaar_name),
                "aadhaar_dob": _none_if_empty(r.aadhaar_dob),
                "salary_slip_name": _none_if_empty(r.salary_slip_name),
                "bank_account_name": _none_if_empty(r.bank_account_name),
            },
        },
        "property_analysis": {
            "under_construction": str(r.property_under_construction) == "True",
            "rera_status": _none_if_empty(r.rera_status) or "unknown",
        },
    }


def run_golden_set_report() -> dict[str, Any]:
    """Runs every golden.csv case through the real compliance_node and
    scores it against the hand-labeled expected flags/rule-status/gate/
    confidence."""
    node_mod.run_compliance_reasoning = lambda rr: "stub"  # no LLM in evaluation
    cfg = get_compliance_config()
    df = pd.read_csv(_GOLDEN_CSV, keep_default_na=False, dtype=str)

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        data = node_mod._extract_compliance_input(_golden_row_to_state(r))
        checks = run_all_checks(data, cfg)
        flags = checks["all_flags"]
        got_codes = sorted({f.code for f in flags})
        got_crit = sorted({s.split(":")[0] for s in checks["critical_flags"]})
        got_rule = "FAIL" if any(f.severity == Severity.CRITICAL for f in flags) else ("WARNING" if flags else "PASS")
        got_gate = "SUSPEND" if checks["critical_flags"] else "PASS"  # emulates Decision Gate 1

        out = node_mod.compliance_node(_golden_row_to_state(r))["compliance_analysis"]
        ComplianceAnalysisResult(**out)  # schema check
        out2 = node_mod.compliance_node(_golden_row_to_state(r))["compliance_analysis"]
        deterministic = out["critical_flags"] == out2["critical_flags"] and out["rule_status"] == out2["rule_status"]

        n_crit = sum(f.severity == Severity.CRITICAL for f in flags)
        n_warn = sum(f.severity in (Severity.MEDIUM, Severity.HIGH) for f in flags)
        exp_conf = max(0.30, min(1.0, 0.90 - 0.15 * n_crit - 0.05 * n_warn))
        exp_codes = sorted(set(json.loads(r.expected_flag_codes)))
        exp_crit = sorted(set(json.loads(r.expected_critical_flags)))

        rows.append({
            "id": r.application_id,
            "codes_ok": got_codes == exp_codes,
            "crit_ok": got_crit == exp_crit,
            "rule_ok": got_rule == r.expected_rule_status,
            "gate_ok": got_gate == r.expected_status,
            "conf_ok": abs(out["confidence"] - exp_conf) < 1e-4,
            "det_ok": deterministic,
            "exp_codes": exp_codes,
            "got_codes": got_codes,
            "exp_rule": r.expected_rule_status,
            "got_rule": got_rule,
            "exp_gate": r.expected_status,
            "got_gate": got_gate,
            "tags": r.edge_case_tags,
        })

    res = pd.DataFrame(rows)
    summary = {
        k: {"passed": int(res[k].sum()), "total": len(res), "pct": round(100 * res[k].mean(), 1)}
        for k in ["codes_ok", "crit_ok", "rule_ok", "gate_ok", "conf_ok", "det_ok"]
    }
    bad_mask = ~(res.codes_ok & res.crit_ok & res.rule_ok & res.gate_ok)
    mismatches = [
        {
            "id": b.id, "expected_codes": b.exp_codes, "expected_rule": b.exp_rule, "expected_gate": b.exp_gate,
            "got_codes": b.got_codes, "got_rule": b.got_rule, "got_gate": b.got_gate, "tags": b.tags,
        }
        for _, b in res[bad_mask].iterrows()
    ]

    allcodes = sorted({c for cs in res.exp_codes for c in cs} | {c for cs in res.got_codes for c in cs})
    per_flag = []
    for c in allcodes:
        tp = int(sum((c in e) and (c in g) for e, g in zip(res.exp_codes, res.got_codes)))
        fn = int(sum((c in e) and (c not in g) for e, g in zip(res.exp_codes, res.got_codes)))
        fp = int(sum((c not in e) and (c in g) for e, g in zip(res.exp_codes, res.got_codes)))
        per_flag.append({
            "code": c, "tp": tp, "fn": fn, "fp": fp,
            "precision": (tp / (tp + fp)) if (tp + fp) else None,
            "recall": (tp / (tp + fn)) if (tp + fn) else None,
        })

    return {
        "sample_size": len(res),
        "summary": summary,
        "mismatches": mismatches,
        "per_flag": per_flag,
    }


def run_name_matcher_report() -> dict[str, Any]:
    """Scores the real fuzzy name matcher against 60 hand-labeled name
    pairs (same/different person, by confusion pattern)."""
    threshold = 90
    df = pd.read_csv(_NAMES_CSV, keep_default_na=False)
    df["score"] = [fuzz.token_sort_ratio(a.lower(), b.lower()) for a, b in zip(df.name_a, df.name_b)]
    df["matcher_says_same"] = [_names_match(a, b, threshold) for a, b in zip(df.name_a, df.name_b)]
    df["flag_raised"] = ~df.matcher_says_same
    df["should_flag"] = df.label == "different_person"

    tp = int((df.flag_raised & df.should_flag).sum())
    fn = int((~df.flag_raised & df.should_flag).sum())
    fp = int((df.flag_raised & ~df.should_flag).sum())
    tn = int((~df.flag_raised & ~df.should_flag).sum())
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None

    misses = []
    for _, r in df[df.flag_raised != df.should_flag].iterrows():
        kind = "false_alarm" if r.flag_raised else "missed_mismatch"
        misses.append({
            "pair_id": r.pair_id, "kind": kind, "name_a": r.name_a, "name_b": r.name_b,
            "pattern": r.pattern, "score": round(float(r.score), 1),
        })

    sweep = []
    for t in (70, 75, 80, 85, 88, 90, 92, 95):
        flag_raised = df.score < t
        tp_t = int((flag_raised & df.should_flag).sum())
        fn_t = int((~flag_raised & df.should_flag).sum())
        fp_t = int((flag_raised & ~df.should_flag).sum())
        sweep.append({
            "threshold": t,
            "precision": (tp_t / (tp_t + fp_t)) if (tp_t + fp_t) else None,
            "recall": (tp_t / (tp_t + fn_t)) if (tp_t + fn_t) else None,
            "fp": fp_t, "fn": fn_t,
        })

    return {
        "sample_size": len(df),
        "threshold": threshold,
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "misses": misses,
        "threshold_sweep": sweep,
    }


def run_compliance_benchmark() -> dict[str, Any]:
    """Full Compliance Agent metrics report: golden rule-engine set + name
    matcher set, both from bundled hand-labeled data - no stored
    applications needed (unlike the credit/property/decision metrics)."""
    return {
        "available": True,
        "golden_set": run_golden_set_report(),
        "name_matcher": run_name_matcher_report(),
    }
