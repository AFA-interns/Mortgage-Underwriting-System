"""Evaluation metrics for the Credit Analysis Agent.

Measurement only - nothing here is imported by the agent, so it can never
change a credit decision. Pure functions over plain dicts, standard library
only (the one exception is `load_confidence_constants`, which tries to read
the live credit_config.yaml and falls back to defaults).

A record is one application:

    {
      "application_id": "APP-1042",
      "credit_analysis": {...},         # CreditAnalysisResult.model_dump()
      "decision": {"decision": "APPROVE"},   # Decision Agent output (or a bare string)
      "gender": "Female",               # audit attribute, NOT a model input
      "field_overrides": {...},         # reviewer corrections, see below
      "outcome_bad": 0 | 1 | None,      # closed-loan outcome, optional
    }

`field_overrides` is either {field: value} or {document_id: {field: value}}.
`None` means "no review data supplied"; `{}` means "reviewable, nothing changed".

Phases: 1 = no outcomes needed, 2 = needs two batches (PSI), 3 = needs
closed-loan outcomes (AUC / Gini / KS / calibration). See CREDIT_METRICS.md.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------
# Vocabulary (mirrors app.models.decision / app.services.credit_bureau)
# --------------------------------------------------------------------------
BUREAU_SOURCES = ("bureau", "applicant_declared", "simulated", "demo_fixture")
CREDIT_DECISIONS = ("APPROVE", "CONDITIONAL", "REJECT")
FINAL_DECISIONS = ("APPROVE", "SUSPEND", "DENY")
# Credit Agent -> the Decision Agent outcome it is expected to line up with.
DECISION_MAP = {"APPROVE": "APPROVE", "CONDITIONAL": "SUSPEND", "REJECT": "DENY"}
SEVERE_CONFLICTS = (("APPROVE", "DENY"), ("REJECT", "APPROVE"))  # (credit, decision)

# Red flags are free-text strings; classify by substring (see
# app.credit.red_flags.detect_red_flags for the exact wording).
FLAG_MARKERS = {
    "settled_account": "settled account",
    "written_off_account": "written-off account",
    "dpd_over_90": "dpd exceeding 90",
    "loan_stacking": "loan stacking",
    "income_to_loan_mismatch": "income-to-loan mismatch",
}
EXPECTED_FLAGS = tuple(FLAG_MARKERS)

CREDIT_BAND_ORDER = ("Excellent", "Good", "Fair", "Poor", "Very Poor")  # best -> worst
RISK_TIER_ORDER = ("low", "moderate", "high")

# Reviewer-editable fields that feed income / obligations (see
# app.document_ingestion.field_overrides.EDITABLE_FIELDS). The credit agent
# itself reads borrower_profile.monthly_income / existing_debt.
UPSTREAM_INCOME_DEBT_FIELDS = frozenset({
    "monthly_income", "existing_debt",
    "gross_salary", "net_salary",                            # salary slip
    "average_monthly_salary_credit", "total_monthly_obligations",  # bank statement
})

_DEFAULT_CONFIDENCE = {
    "base": 0.90, "no_credit_history_penalty": 0.30, "per_red_flag_penalty": 0.05, "floor": 0.30,
}

AIR_THRESHOLD = 0.80
PSI_STABLE, PSI_SHIFT = 0.10, 0.25
PSI_EPSILON = 1e-4


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _pct(n: float, total: float) -> float:
    return round(100.0 * n / total, 2) if total else 0.0


def _upper(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):  # enum
        value = value.value
    text = str(value).strip().upper()
    return text or None


def _credit(rec: dict[str, Any]) -> dict[str, Any]:
    return rec.get("credit_analysis") or {}


def _credit_decision(rec: dict[str, Any]) -> str | None:
    return _upper(_credit(rec).get("preliminary_decision"))


def _final_decision(rec: dict[str, Any]) -> str | None:
    dec = rec.get("decision")
    if isinstance(dec, dict):
        dec = dec.get("decision")
    return _upper(dec)


def _label(rec: dict[str, Any]) -> int | None:
    v = rec.get("outcome_bad")
    if v is None:
        return None
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if v in (0, 1) else None


def _bureau_source(rec: dict[str, Any]) -> str:
    src = (_credit(rec).get("raw_data") or {}).get("bureau_source")
    return src if src in BUREAU_SOURCES else "unknown"


def classify_flag(flag: Any) -> str:
    """Maps a red-flag string (or dict with a 'code'/'message') to a category."""
    if isinstance(flag, dict):
        flag = flag.get("code") or flag.get("message") or ""
    text = str(flag).lower()
    for name, marker in FLAG_MARKERS.items():
        if marker in text or name in text:
            return name
    return "other"


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    """Flattens one exported `applications` row (full application in the JSONB
    `view` column) into the record shape above. Already-flat records pass
    through unchanged. Extra columns on the row (`gender`, `field_overrides`,
    `outcome_bad`) are carried over - see scripts/credit_metrics_report.py for
    the export SQL."""
    view = row.get("view")
    if isinstance(view, str):
        import json
        view = json.loads(view)
    if not isinstance(view, dict):
        return dict(row)

    agents = view.get("agents") or {}
    decision = agents.get("decision") or view.get("decision") or {}
    return {
        "application_id": row.get("id") or view.get("id"),
        "created_at": row.get("created_at") or view.get("created_at"),
        "credit_analysis": agents.get("credit") or {},
        "decision": decision,
        "gender": row.get("gender") or view.get("gender"),
        "field_overrides": row.get("field_overrides"),
        "outcome_bad": row.get("outcome_bad"),
    }


def normalize_records(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_record(r) for r in rows]


def load_confidence_constants() -> dict[str, float]:
    """credit_config.yaml::confidence if readable, else the documented defaults."""
    try:
        from app.credit.config import get_credit_config

        cfg = get_credit_config().get("confidence") or {}
        return {k: float(cfg.get(k, v)) for k, v in _DEFAULT_CONFIDENCE.items()}
    except Exception:  # missing yaml/dependency - metrics must still import
        return dict(_DEFAULT_CONFIDENCE)


# --------------------------------------------------------------------------
# PHASE 1
# --------------------------------------------------------------------------
def bureau_source_mix(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(_bureau_source(r) for r in records)
    total = len(records)
    keys = (*BUREAU_SOURCES, "unknown")
    sources = {k: {"count": counts.get(k, 0), "pct": _pct(counts.get(k, 0), total)} for k in keys}
    unverified = sum(counts.get(k, 0) for k in ("applicant_declared", "simulated", "demo_fixture"))
    return {
        "total": total,
        "sources": sources,
        "simulated_share_pct": sources["simulated"]["pct"],
        "unverified_share_pct": _pct(unverified, total),
        "meets_production_target": total > 0 and counts.get("simulated", 0) == 0,
    }


def flag_trigger_rates(
    records: Sequence[dict[str, Any]], expected_flags: Sequence[str] | None = None
) -> dict[str, Any]:
    total = len(records)
    counts: Counter[str] = Counter()
    for r in records:
        for cat in {classify_flag(f) for f in (_credit(r).get("flags") or [])}:
            counts[cat] += 1  # applications carrying the flag, not raw flag count
    names = list(expected_flags if expected_flags is not None else EXPECTED_FLAGS)
    names += [k for k in counts if k not in names]
    return {
        "total": total,
        "flags": {n: {"count": counts.get(n, 0), "pct": _pct(counts.get(n, 0), total)} for n in names},
        "applications_with_any_flag": sum(1 for r in records if _credit(r).get("flags")),
    }


def decision_distribution(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    decided = [d for d in (_credit_decision(r) for r in records) if d]
    counts = Counter(decided)
    total = len(decided)
    out = {k: {"count": counts.get(k, 0), "pct": _pct(counts.get(k, 0), total)} for k in CREDIT_DECISIONS}
    other = total - sum(counts.get(k, 0) for k in CREDIT_DECISIONS)
    return {"total": total, "missing_decision": len(records) - total, "other": other, "decisions": out}


def expected_confidence(cibil_score: int | None, flag_count: int, constants: dict[str, float] | None = None) -> float:
    c = constants or load_confidence_constants()
    score = c["base"] - (c["no_credit_history_penalty"] if cibil_score is None else 0.0)
    score -= flag_count * c["per_red_flag_penalty"]
    return round(max(c["floor"], min(1.0, score)), 2)


def confidence_distribution(
    records: Sequence[dict[str, Any]],
    constants: dict[str, float] | None = None,
    floor_alert_pct: float = 20.0,
    tolerance: float = 0.005,
) -> dict[str, Any]:
    c = constants or load_confidence_constants()
    floor = c["floor"]
    bins = [0] * 20  # 0.05 wide
    at_floor = 0
    mismatches: list[dict[str, Any]] = []
    n = 0
    for r in records:
        ca = _credit(r)
        if ca.get("confidence") is None or ca.get("preliminary_decision") is None:
            continue  # empty result from the missing-data short-circuit
        n += 1
        conf = float(ca["confidence"])
        bins[min(19, max(0, int(conf / 0.05 + 1e-9)))] += 1
        if conf <= floor + 1e-9:
            at_floor += 1
        exp = expected_confidence(ca.get("cibil_score"), len(ca.get("flags") or []), c)
        if abs(exp - conf) > tolerance:
            mismatches.append({
                "application_id": r.get("application_id"),
                "stored": conf, "expected": exp,
            })
    at_floor_pct = _pct(at_floor, n)
    return {
        "n": n,
        "histogram": [
            {"bin": f"{i * 0.05:.2f}-{(i + 1) * 0.05:.2f}", "count": b, "pct": _pct(b, n)}
            for i, b in enumerate(bins)
        ],
        "at_floor_count": at_floor,
        "at_floor_pct": at_floor_pct,
        "floor_alert": n > 0 and at_floor_pct > floor_alert_pct,
        "formula": c,
        "formula_mismatches": mismatches,
    }


def agreement_matrix(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    matrix = {c: {d: 0 for d in FINAL_DECISIONS} for c in CREDIT_DECISIONS}
    off_diagonal: list[dict[str, Any]] = []
    severe: list[dict[str, Any]] = []
    skipped = 0
    compared = agree = 0
    for r in records:
        c, d = _credit_decision(r), _final_decision(r)
        if c not in matrix or d not in FINAL_DECISIONS:
            skipped += 1
            continue
        matrix[c][d] += 1
        compared += 1
        if DECISION_MAP[c] == d:
            agree += 1
            continue
        case = {"application_id": r.get("application_id"), "credit": c, "decision": d}
        off_diagonal.append(case)
        if (c, d) in SEVERE_CONFLICTS:
            severe.append(case)
    return {
        "mapping": DECISION_MAP,
        "rows": list(CREDIT_DECISIONS), "cols": list(FINAL_DECISIONS),
        "matrix": matrix,
        "compared": compared, "skipped": skipped,
        "agreement_rate_pct": _pct(agree, compared),
        "off_diagonal": off_diagonal,
        "severe_conflicts": severe,
    }


def _flatten_overrides(overrides: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            if isinstance(v, dict):
                keys |= _flatten_overrides(v)
            else:
                keys.add(str(k))
    return keys


def upstream_data_quality_rate(
    records: Sequence[dict[str, Any]], fields: Iterable[str] = UPSTREAM_INCOME_DEBT_FIELDS
) -> dict[str, Any]:
    fields = set(fields)
    reviewed = [r for r in records if r.get("field_overrides") is not None]
    hit: list[str | None] = []
    by_field: Counter[str] = Counter()
    for r in reviewed:
        touched = _flatten_overrides(r["field_overrides"]) & fields
        if touched:
            hit.append(r.get("application_id"))
            by_field.update(touched)
    return {
        "reviewed": len(reviewed),
        "not_reviewed": len(records) - len(reviewed),
        "overridden": len(hit),
        "rate_pct": _pct(len(hit), len(reviewed)),
        "by_field": dict(by_field),
        "application_ids": hit,
        "fields_watched": sorted(fields),
    }


def adverse_impact_ratio(
    records: Sequence[dict[str, Any]],
    group_key: str = "gender",
    decision_source: str = "credit",
    min_group_size: int = 30,
) -> dict[str, Any]:
    """Audit-only. Must be run OUTSIDE the agent's decision path - the group
    attribute is never an input to credit_node. `decision_source` is "credit"
    (preliminary_decision) or "decision" (Decision Agent, APPROVE only)."""
    groups: dict[str, dict[str, int]] = {}
    for r in records:
        dec = _credit_decision(r) if decision_source == "credit" else _final_decision(r)
        if dec is None:
            continue
        g = r.get(group_key)
        g = str(g).strip() if g not in (None, "") else "unknown"
        s = groups.setdefault(g, {"n": 0, "approve": 0, "approve_or_conditional": 0})
        s["n"] += 1
        if dec == "APPROVE":
            s["approve"] += 1
        if dec in ("APPROVE", "CONDITIONAL"):
            s["approve_or_conditional"] += 1

    def _air(key: str) -> dict[str, Any]:
        known = {g: s for g, s in groups.items() if g != "unknown" and s["n"] > 0}
        rates = {g: s[key] / s["n"] for g, s in known.items()}
        out: dict[str, Any] = {"rates_pct": {g: round(100 * v, 2) for g, v in rates.items()}}
        if len(rates) < 2:
            out.update(air=None, status="insufficient_groups", flagged=False)
            return out
        hi_g, lo_g = max(rates, key=rates.get), min(rates, key=rates.get)
        if rates[hi_g] == 0:
            out.update(air=None, status="undefined_zero_favourable_rate", flagged=False)
            return out
        air = rates[lo_g] / rates[hi_g]
        out.update(
            air=round(air, 4), lowest_group=lo_g, highest_group=hi_g,
            flagged=air < AIR_THRESHOLD, status="below_threshold" if air < AIR_THRESHOLD else "ok",
        )
        return out

    small = [g for g, s in groups.items() if g != "unknown" and s["n"] < min_group_size]
    return {
        "group_key": group_key,
        "decision_source": decision_source,
        "threshold": AIR_THRESHOLD,
        "groups": groups,
        "favourable_approve": _air("approve"),
        "favourable_approve_or_conditional": _air("approve_or_conditional"),
        "small_groups": small,
        "note": (
            "Below 0.80 is a trigger for investigation, not proof of discrimination. "
            "The four-fifths rule is a US screening benchmark, not an Indian regulation."
            + (f" Groups under {min_group_size} applications are statistically unreliable: {small}." if small else "")
        ),
    }


def phase1_report(
    records: Sequence[dict[str, Any]],
    group_key: str = "gender",
    expected_flags: Sequence[str] | None = None,
    constants: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "n_applications": len(records),
        "bureau_source_mix": bureau_source_mix(records),
        "flag_trigger_rates": flag_trigger_rates(records, expected_flags),
        "decision_distribution": decision_distribution(records),
        "confidence_distribution": confidence_distribution(records, constants),
        "agreement_matrix": agreement_matrix(records),
        "upstream_data_quality_rate": upstream_data_quality_rate(records),
        "adverse_impact_ratio": adverse_impact_ratio(records, group_key),
    }


# --------------------------------------------------------------------------
# PHASE 2 - drift
# --------------------------------------------------------------------------
def quantile_edges(baseline_values: Sequence[float], n_bins: int = 10) -> list[float]:
    """Interior cut points (descending, de-duplicated) giving ~equal-count bands
    on the baseline. n_bins bands -> up to n_bins - 1 edges."""
    vals = sorted(baseline_values)
    if not vals or n_bins < 2:
        return []
    edges: list[float] = []
    for i in range(1, n_bins):
        pos = (len(vals) - 1) * i / n_bins
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(vals) - 1)
        edges.append(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo))
    return sorted(set(edges), reverse=True)


def band_index(value: float, edges: Sequence[float]) -> int:
    """Descending edges [80, 65, 50] -> bands >=80, [65,80), [50,65), <50."""
    for i, e in enumerate(sorted(edges, reverse=True)):
        if value >= e:
            return i
    return len(edges)


def band_shares(values: Sequence[float], edges: Sequence[float]) -> list[float]:
    counts = [0] * (len(edges) + 1)
    for v in values:
        counts[band_index(v, edges)] += 1
    total = sum(counts)
    return [c / total if total else 0.0 for c in counts]


def psi_status(value: float) -> str:
    if value < PSI_STABLE:
        return "stable"
    if value <= PSI_SHIFT:
        return "moderate shift"  # investigate
    return "significant shift"


def psi_from_shares(base: Sequence[float], cur: Sequence[float]) -> float:
    if len(base) != len(cur):
        raise ValueError("baseline and current need the same number of bands")
    total = 0.0
    for b, c in zip(base, cur):
        b, c = (b if b > 0 else PSI_EPSILON), (c if c > 0 else PSI_EPSILON)
        total += (c - b) * math.log(c / b)
    return total


def psi(baseline: Sequence[float], current: Sequence[float], edges: Sequence[float]) -> dict[str, Any]:
    if not baseline or not current:
        return {"available": False, "reason": "PSI needs a non-empty baseline and current batch."}
    b, c = band_shares(baseline, edges), band_shares(current, edges)
    value = psi_from_shares(b, c)
    return {
        "available": True,
        "psi": round(value, 4),
        "status": psi_status(value),
        "edges": sorted(edges, reverse=True),
        "baseline_shares": [round(x, 4) for x in b],
        "current_shares": [round(x, 4) for x in c],
        "n_baseline": len(baseline), "n_current": len(current),
    }


# --------------------------------------------------------------------------
# PHASE 3 - outcomes (label 1 = Bad, 0 = Good; higher score = better)
# --------------------------------------------------------------------------
def _split(scores: Sequence[float], labels: Sequence[int]) -> tuple[list[float], list[float]]:
    good = [s for s, y in zip(scores, labels) if y == 0]
    bad = [s for s, y in zip(scores, labels) if y == 1]
    return good, bad


def auc(scores: Sequence[float], labels: Sequence[int]) -> float | None:
    """P(random Good scores above random Bad); ties count half (Mann-Whitney)."""
    good, bad = _split(scores, labels)
    if not good or not bad:
        return None
    pairs = sorted((s, y) for s, y in zip(scores, labels))
    rank_sum_good = 0.0
    i = 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2  # average of ranks i+1..j
        rank_sum_good += avg_rank * sum(1 for k in range(i, j) if pairs[k][1] == 0)
        i = j
    n_g, n_b = len(good), len(bad)
    return (rank_sum_good - n_g * (n_g + 1) / 2) / (n_g * n_b)


def gini(auc_value: float | None) -> float | None:
    return None if auc_value is None else 2 * (auc_value - 0.5)


def ks_statistic(scores: Sequence[float], labels: Sequence[int], edges: Sequence[float] | None = None) -> float | None:
    """max |cum%Good - cum%Bad| walking from the top score down. With `edges`
    (descending band cut-offs) the walk is per band instead of per distinct score.
    Returned as a fraction (0.60 = 60%)."""
    good, bad = _split(scores, labels)
    if not good or not bad:
        return None
    if edges is not None:
        keys = [band_index(s, edges) for s in scores]
        steps = range(len(edges) + 1)
    else:
        keys = [-s for s in scores]
        steps = sorted(set(keys))
    cg = cb = 0
    best = 0.0
    for step in steps:
        cg += sum(1 for k, y in zip(keys, labels) if k == step and y == 0)
        cb += sum(1 for k, y in zip(keys, labels) if k == step and y == 1)
        best = max(best, abs(cg / len(good) - cb / len(bad)))
    return best


def auc_status(value: float | None) -> str | None:
    if value is None:
        return None
    return "good" if value > 0.80 else "acceptable" if value > 0.70 else "weak"


def ks_status(value: float | None) -> str | None:
    """`value` is a fraction; thresholds are 25% / 20%."""
    if value is None:
        return None
    pct = value * 100
    return "good" if pct > 25 else "acceptable" if pct >= 20 else "weak"


def bad_rate_by_group(records: Sequence[dict[str, Any]], field: str, order: Sequence[str]) -> dict[str, Any]:
    stats = {g: {"n": 0, "bad": 0} for g in order}
    other: dict[str, dict[str, int]] = {}
    for r in records:
        y = _label(r)
        if y is None:
            continue
        g = _credit(r).get(field)
        s = stats.get(g) if g in stats else other.setdefault(str(g), {"n": 0, "bad": 0})
        s["n"] += 1
        s["bad"] += y
    for s in (*stats.values(), *other.values()):
        s["bad_rate_pct"] = _pct(s["bad"], s["n"]) if s["n"] else None
    present = [(g, stats[g]["bad_rate_pct"]) for g in order if stats[g]["n"]]
    violations = [
        {"from": a[0], "to": b[0], "from_rate_pct": a[1], "to_rate_pct": b[1]}
        for a, b in zip(present, present[1:]) if b[1] < a[1]
    ]
    return {
        "field": field, "order": list(order), "groups": stats, "not_in_order": other,
        "monotonic": not violations, "violations": violations,
    }


def _correct(decision: str | None, y: int) -> bool | None:
    if decision == "APPROVE":
        return y == 0
    if decision == "REJECT":
        return y == 1
    return None  # CONDITIONAL is a referral - neither right nor wrong on outcome alone


def confidence_calibration(
    records: Sequence[dict[str, Any]],
    edges: Sequence[float] = (0.3, 0.5, 0.7, 0.9, 1.0001),
    tolerance: float = 0.10,
) -> dict[str, Any]:
    """Compares mean stated confidence with how often the agent's definite calls
    (APPROVE / REJECT) matched the realised outcome. Note: `confidence` measures
    evidence quality, not probability of being right, so poor calibration is a
    finding about the definition, not necessarily a bug."""
    buckets = [{"low": a, "high": b, "n": 0, "conf_sum": 0.0, "correct": 0} for a, b in zip(edges, edges[1:])]
    for r in records:
        y = _label(r)
        ca = _credit(r)
        if y is None or ca.get("confidence") is None:
            continue
        ok = _correct(_credit_decision(r), y)
        if ok is None:
            continue
        for b in buckets:
            if b["low"] <= ca["confidence"] < b["high"]:
                b["n"] += 1
                b["conf_sum"] += ca["confidence"]
                b["correct"] += int(ok)
                break
    out = []
    for b in buckets:
        row = {"range": f"{b['low']:.2f}-{min(b['high'], 1.0):.2f}", "n": b["n"]}
        if b["n"]:
            mean_conf, acc = b["conf_sum"] / b["n"], b["correct"] / b["n"]
            row.update(
                mean_confidence=round(mean_conf, 3), realised_correct=round(acc, 3),
                gap=round(mean_conf - acc, 3), well_calibrated=abs(mean_conf - acc) <= tolerance,
            )
        else:
            row.update(mean_confidence=None, realised_correct=None, gap=None, well_calibrated=None)
        out.append(row)
    return {"tolerance": tolerance, "buckets": out}


def outcome_report(records: Sequence[dict[str, Any]], edges: Sequence[float] | None = None) -> dict[str, Any]:
    labelled = [r for r in records if _label(r) is not None and _credit(r).get("risk_score") is not None]
    if not labelled:
        return {
            "available": False,
            "reason": "No records carry an outcome_bad label (1 = Bad, 0 = Good). "
                      "Outcome metrics need closed-loan performance data; none are invented.",
        }
    scores = [float(_credit(r)["risk_score"]) for r in labelled]
    labels = [_label(r) for r in labelled]
    n_bad = sum(labels)
    a = auc(scores, labels)
    ks_exact = ks_statistic(scores, labels)
    ks = ks_statistic(scores, labels, edges) if edges is not None else ks_exact
    warnings = []
    if n_bad == 0 or n_bad == len(labels):
        warnings.append("Only one outcome class present - AUC/KS undefined.")
    elif n_bad < 30:
        warnings.append(f"Only {n_bad} Bad outcomes - estimates are unstable.")
    g = gini(a)
    return {
        "available": True,
        "n_labelled": len(labelled), "n_bad": n_bad, "n_good": len(labels) - n_bad,
        "auc": None if a is None else round(a, 4), "auc_status": auc_status(a),
        "gini": None if g is None else round(g, 4),
        "ks": None if ks is None else round(ks, 4), "ks_status": ks_status(ks),
        "ks_basis": "banded" if edges is not None else "exact",
        "ks_exact": None if ks_exact is None else round(ks_exact, 4),
        "bad_rate_by_credit_band": bad_rate_by_group(labelled, "credit_band", CREDIT_BAND_ORDER),
        "bad_rate_by_credit_risk_tier": bad_rate_by_group(labelled, "credit_risk_tier", RISK_TIER_ORDER),
        "confidence_calibration": confidence_calibration(labelled),
        "warnings": warnings,
    }
