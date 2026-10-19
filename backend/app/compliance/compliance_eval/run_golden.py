# ruff: noqa: E401, E402
"""Run the golden CSV through the Compliance Agent and score it.
Usage (from backend/):  python app/compliance/compliance_eval/run_golden.py [golden_csv] [results_csv]
Defaults to data/golden.csv next to this script; writes a results file only if results_csv is given."""
import sys, json, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
BACKEND = next(p for p in HERE.parents if (p / 'app' / 'compliance').is_dir())   # finds backend/ wherever this folder lives
csv_path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'data' / 'golden.csv')
sys.path.insert(0, str(BACKEND))
import pandas as pd
import app.graph.nodes.compliance as node_mod
from app.compliance.config import get_compliance_config
from app.compliance.rules_engine import run_all_checks
from app.compliance.scoring import compute_confidence
from app.models.decision import ComplianceAnalysisResult, Severity

node_mod.run_compliance_reasoning = lambda rr: "stub"   # no LLM in evaluation
cfg = get_compliance_config()

def none_if_empty(v): return None if v == "" else v

def to_state(r):
    raw = json.loads(r.raw_fields)
    docs = json.loads(r.kyc_documents) if r.kyc_documents else []
    return {
        "application_id": r.application_id,
        "borrower_profile": {**raw, "loan_amount": int(r.loan_amount_inr), "property_city_tier": none_if_empty(r.property_city_tier)},
        "document_analysis": {
            "kyc": {"documents": docs, "pmla": {
                "source_of_funds_declared": r.pmla_source_of_funds_declared is True or str(r.pmla_source_of_funds_declared) == "True",
                "identity_verification_logged": str(r.pmla_identity_verification_log_present) == "True"}},
            "borrower_identity": {
                "application_form_name": none_if_empty(r.application_name), "application_form_dob": none_if_empty(r.application_dob),
                "application_form_pan_number": none_if_empty(r.application_pan),
                "pan_card_name": none_if_empty(r.pan_name), "pan_card_number": none_if_empty(r.pan_card_number),
                "aadhaar_name": none_if_empty(r.aadhaar_name), "aadhaar_dob": none_if_empty(r.aadhaar_dob),
                "salary_slip_name": none_if_empty(r.salary_slip_name), "bank_account_name": none_if_empty(r.bank_account_name)}},
        "property_analysis": {"under_construction": str(r.property_under_construction) == "True",
                              "rera_status": none_if_empty(r.rera_status) or "unknown"},
    }

df = pd.read_csv(csv_path, keep_default_na=False, dtype=str)
rows, failures = [], []
for _, r in df.iterrows():
    st = to_state(r)
    data = node_mod._extract_compliance_input(st)
    checks = run_all_checks(data, cfg)
    flags = checks["all_flags"]
    got_codes = sorted({f.code for f in flags})
    got_crit = sorted({s.split(":")[0] for s in checks["critical_flags"]})
    got_rule = "FAIL" if any(f.severity == Severity.CRITICAL for f in flags) else ("WARNING" if flags else "PASS")
    got_gate = "SUSPEND" if checks["critical_flags"] else "PASS"          # emulates Decision Gate 1
    out = node_mod.compliance_node(to_state(r))["compliance_analysis"]
    ComplianceAnalysisResult(**out)                                        # schema check
    out2 = node_mod.compliance_node(to_state(r))["compliance_analysis"]
    deterministic = (out["critical_flags"] == out2["critical_flags"] and out["rule_status"] == out2["rule_status"])
    n_crit = sum(f.severity == Severity.CRITICAL for f in flags); n_warn = sum(f.severity in (Severity.MEDIUM, Severity.HIGH) for f in flags)
    exp_conf = max(0.30, min(1.0, 0.90 - 0.15*n_crit - 0.05*n_warn))
    exp_codes = sorted(set(json.loads(r.expected_flag_codes))); exp_crit = sorted(set(json.loads(r.expected_critical_flags)))
    rec = dict(id=r.application_id, codes_ok=got_codes == exp_codes, crit_ok=got_crit == exp_crit, rule_ok=got_rule == r.expected_rule_status,
               gate_ok=got_gate == r.expected_status, conf_ok=abs(out["confidence"] - exp_conf) < 1e-4, det_ok=deterministic,
               exp_codes=exp_codes, got_codes=got_codes, exp_rule=r.expected_rule_status, got_rule=got_rule, exp_gate=r.expected_status, got_gate=got_gate,
               node_nhb=out["rule_status"].get("nhb"), tags=r.edge_case_tags)
    rows.append(rec)
res = pd.DataFrame(rows)
print(f"cases: {len(res)}")
for k in ["codes_ok","crit_ok","rule_ok","gate_ok","conf_ok","det_ok"]:
    print(f"  {k:9s} {res[k].sum()}/{len(res)}  ({100*res[k].mean():.1f}%)")
bad = res[~(res.codes_ok & res.crit_ok & res.rule_ok & res.gate_ok)]
print(f"\nmismatching cases: {len(bad)}")
for _, b in bad.iterrows():
    print(f"  {b.id}: expected codes={b.exp_codes} rule={b.exp_rule} gate={b.exp_gate} | got codes={b.got_codes} rule={b.got_rule} gate={b.got_gate} | tags={b.tags}")
if len(sys.argv) > 2:
    res.to_csv(sys.argv[2], index=False)
    print(f"results written to {sys.argv[2]}")

# per-flag recall / precision on code sets
print("\nper-flag (set-level) recall / precision:")
allcodes = sorted({c for l in res.exp_codes for c in l} | {c for l in res.got_codes for c in l})
for c in allcodes:
    tp = sum((c in e) and (c in g) for e, g in zip(res.exp_codes, res.got_codes))
    fn = sum((c in e) and (c not in g) for e, g in zip(res.exp_codes, res.got_codes))
    fp = sum((c not in e) and (c in g) for e, g in zip(res.exp_codes, res.got_codes))
    print(f"  {c:36s} TP={tp:2d} FN={fn} FP={fp}")
