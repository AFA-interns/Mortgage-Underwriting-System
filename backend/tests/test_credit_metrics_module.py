"""Pure unit tests for app.credit.metrics (no DB, no credit_node).

Every dataset below is hand-built for the test - none of it is real
applicant data or real model performance.
"""
import pytest

from app.credit import metrics as m

DEFAULTS = {"base": 0.90, "no_credit_history_penalty": 0.30, "per_red_flag_penalty": 0.05, "floor": 0.30}


def rec(app_id="A", credit="APPROVE", decision="APPROVE", source="bureau", flags=(), conf=0.9,
        cibil=780, score=80.0, band="Excellent", tier="low", gender=None, overrides=None, bad=None):
    return {
        "application_id": app_id,
        "credit_analysis": {
            "preliminary_decision": credit, "confidence": conf, "cibil_score": cibil,
            "flags": list(flags), "risk_score": score, "credit_band": band,
            "credit_risk_tier": tier, "raw_data": {"bureau_source": source},
        },
        "decision": {"decision": decision},
        "gender": gender, "field_overrides": overrides, "outcome_bad": bad,
    }


# ---- toy dataset from the metrics document ---------------------------------
TOY = [(92, 0), (88, 0), (81, 0), (74, 0), (68, 1), (61, 0), (55, 1), (47, 1), (39, 1), (28, 1)]
TOY_SCORES, TOY_LABELS = [s for s, _ in TOY], [y for _, y in TOY]


def test_auc_gini_ks_match_document_toy_values():
    a = m.auc(TOY_SCORES, TOY_LABELS)
    assert a == pytest.approx(0.96)
    assert m.gini(a) == pytest.approx(0.92)
    assert m.ks_statistic(TOY_SCORES, TOY_LABELS, edges=[80, 65, 50]) == pytest.approx(0.60)
    # Per-distinct-score KS is higher (0.80, after the 74 score) - the document's
    # 0.60 is the BAND-based figure, so the two must not be mixed up.
    assert m.ks_statistic(TOY_SCORES, TOY_LABELS) == pytest.approx(0.80)


def test_auc_ties_count_half_and_degenerate_inputs():
    assert m.auc([50, 50], [0, 1]) == pytest.approx(0.5)
    assert m.auc([1, 2, 3], [0, 0, 0]) is None
    assert m.ks_statistic([1, 2], [1, 1]) is None
    assert m.gini(None) is None


def test_status_thresholds():
    assert [m.auc_status(x) for x in (0.85, 0.75, 0.70, None)] == ["good", "acceptable", "weak", None]
    assert [m.ks_status(x) for x in (0.30, 0.22, 0.20, 0.10, None)] == ["good", "acceptable", "acceptable", "weak", None]


# ---- PSI -------------------------------------------------------------------
def test_psi_from_document_shares():
    value = m.psi_from_shares([0.60, 0.30, 0.10], [0.40, 0.35, 0.25])
    assert value == pytest.approx(0.226, abs=0.001)
    assert m.psi_status(value) == "moderate shift"


def test_psi_status_bands_and_empty_band_epsilon():
    assert m.psi_status(0.05) == "stable"
    assert m.psi_status(0.30) == "significant shift"
    assert m.psi_from_shares([0.5, 0.5, 0.0], [0.5, 0.0, 0.5]) > 0.25  # no log(0) / div-by-zero


def test_psi_on_values_identical_batches_is_zero():
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95]
    edges = m.quantile_edges(vals, 4)
    out = m.psi(vals, vals, edges)
    assert out["psi"] == 0 and out["status"] == "stable"


def test_psi_requires_both_batches():
    assert m.psi([], [1.0], [0.5])["available"] is False


def test_quantile_edges_descending_deduped():
    edges = m.quantile_edges(list(range(1, 101)), 4)
    assert len(edges) == 3 and edges == sorted(edges, reverse=True)
    assert m.quantile_edges([5, 5, 5, 5], 4) == [5]
    assert m.quantile_edges([], 4) == []


# ---- confidence ------------------------------------------------------------
def test_expected_confidence_formula():
    assert m.expected_confidence(None, 2, DEFAULTS) == 0.50   # no history + 2 flags
    assert m.expected_confidence(780, 0, DEFAULTS) == 0.90
    assert m.expected_confidence(None, 20, DEFAULTS) == 0.30  # floor
    assert m.expected_confidence(780, 0, {**DEFAULTS, "base": 1.4}) == 1.0  # cap


def test_confidence_distribution_floor_alert_and_mismatches():
    rows = [rec(f"F{i}", conf=0.30, cibil=None, flags=["x"] * 12) for i in range(3)]
    rows += [rec("OK", conf=0.90), rec("BAD", conf=0.60)]  # BAD: formula says 0.90
    out = m.confidence_distribution(rows, DEFAULTS)
    assert out["n"] == 5
    assert out["at_floor_count"] == 3 and out["at_floor_pct"] == 60.0
    assert out["floor_alert"] is True
    assert [x["application_id"] for x in out["formula_mismatches"]] == ["BAD"]
    assert sum(b["count"] for b in out["histogram"]) == 5
    assert len(out["histogram"]) == 20


def test_confidence_distribution_no_alert_when_few_at_floor():
    rows = [rec(f"R{i}", conf=0.90) for i in range(9)] + [rec("F", conf=0.30, cibil=None, flags=["x"] * 12)]
    out = m.confidence_distribution(rows, DEFAULTS)
    assert out["at_floor_pct"] == 10.0 and out["floor_alert"] is False


def test_confidence_one_point_zero_lands_in_last_bin():
    out = m.confidence_distribution([rec(conf=1.0)], {**DEFAULTS, "base": 1.0})
    assert out["histogram"][-1]["count"] == 1


# ---- bureau source mix -----------------------------------------------------
def test_bureau_source_mix_counts_and_target():
    rows = [rec(source="bureau"), rec(source="simulated"), rec(source="simulated"),
            rec(source="applicant_declared"), rec(source="demo_fixture"), rec(source="provided")]
    out = m.bureau_source_mix(rows)
    assert out["sources"]["simulated"] == {"count": 2, "pct": 33.33}
    assert out["sources"]["unknown"]["count"] == 1
    assert out["simulated_share_pct"] == 33.33
    assert out["meets_production_target"] is False


def test_bureau_source_mix_production_target_met_and_empty():
    assert m.bureau_source_mix([rec(source="bureau")])["meets_production_target"] is True
    empty = m.bureau_source_mix([])
    assert empty["meets_production_target"] is False and empty["total"] == 0


# ---- flags / decisions -----------------------------------------------------
def test_flag_trigger_rates_include_zero_rate_flags():
    rows = [
        rec(flags=["1 settled account(s) found in credit history",
                   "DPD exceeding 90 days in last 12 months (max DPD: 120)"]),
        rec(flags=["Possible loan stacking - 4 credit enquiries in last 90 days"]),
        rec(), rec(),
    ]
    out = m.flag_trigger_rates(rows)
    assert out["flags"]["settled_account"] == {"count": 1, "pct": 25.0}
    assert out["flags"]["loan_stacking"]["count"] == 1
    assert out["flags"]["written_off_account"] == {"count": 0, "pct": 0.0}
    assert out["applications_with_any_flag"] == 2
    custom = m.flag_trigger_rates(rows, expected_flags=["never_seen"])
    assert custom["flags"]["never_seen"]["count"] == 0 and "settled_account" in custom["flags"]


def test_classify_flag_variants():
    assert m.classify_flag({"code": "written_off_account"}) == "written_off_account"
    assert m.classify_flag("Requested loan ... income-to-loan mismatch") == "income_to_loan_mismatch"
    assert m.classify_flag("something new") == "other"


def test_decision_distribution():
    rows = [rec(credit="APPROVE"), rec(credit="APPROVE"), rec(credit="REJECT"), rec(credit=None)]
    out = m.decision_distribution(rows)
    assert out["total"] == 3 and out["missing_decision"] == 1
    assert out["decisions"]["APPROVE"] == {"count": 2, "pct": 66.67}
    assert out["decisions"]["CONDITIONAL"]["count"] == 0


# ---- agreement matrix ------------------------------------------------------
def test_agreement_matrix_and_severe_conflicts():
    rows = [
        rec("1", "APPROVE", "APPROVE"), rec("2", "CONDITIONAL", "SUSPEND"), rec("3", "REJECT", "DENY"),
        rec("4", "APPROVE", "DENY"),       # severe
        rec("5", "REJECT", "APPROVE"),     # severe
        rec("6", "CONDITIONAL", "APPROVE"),  # off-diagonal, not severe
        rec("7", "APPROVE", None),         # skipped
    ]
    out = m.agreement_matrix(rows)
    assert out["compared"] == 6 and out["skipped"] == 1
    assert out["agreement_rate_pct"] == 50.0
    assert out["matrix"]["APPROVE"]["DENY"] == 1
    assert {c["application_id"] for c in out["off_diagonal"]} == {"4", "5", "6"}
    assert {c["application_id"] for c in out["severe_conflicts"]} == {"4", "5"}


def test_agreement_accepts_bare_string_decision_and_empty_input():
    r = rec("1", "APPROVE")
    r["decision"] = "approve"
    assert m.agreement_matrix([r])["agreement_rate_pct"] == 100.0
    assert m.agreement_matrix([])["compared"] == 0


# ---- upstream data quality -------------------------------------------------
def test_upstream_data_quality_rate():
    rows = [
        rec("1", overrides={"doc-a": {"net_salary": 90000}}),
        rec("2", overrides={"doc-a": {"full_name": "X"}}),   # reviewed, irrelevant field
        rec("3", overrides={}),                              # reviewed, nothing changed
        rec("4", overrides={"existing_debt": 5000}),         # flat shape
        rec("5", overrides=None),                            # not reviewed
    ]
    out = m.upstream_data_quality_rate(rows)
    assert out["reviewed"] == 4 and out["not_reviewed"] == 1
    assert out["overridden"] == 2 and out["rate_pct"] == 50.0
    assert out["by_field"] == {"net_salary": 1, "existing_debt": 1}
    assert m.upstream_data_quality_rate([])["rate_pct"] == 0.0


# ---- adverse impact ratio --------------------------------------------------
def _group_rows(male_approve, male_total, female_approve, female_total):
    rows = []
    for i in range(male_total):
        rows.append(rec(f"M{i}", "APPROVE" if i < male_approve else "REJECT", gender="Male"))
    for i in range(female_total):
        rows.append(rec(f"F{i}", "APPROVE" if i < female_approve else "REJECT", gender="Female"))
    return rows


def test_air_flags_below_four_fifths():
    out = m.adverse_impact_ratio(_group_rows(60, 100, 30, 100))  # 60% vs 30% -> 0.5
    fav = out["favourable_approve"]
    assert fav["air"] == 0.5 and fav["flagged"] is True
    assert fav["lowest_group"] == "Female" and fav["highest_group"] == "Male"
    assert "not proof of discrimination" in out["note"]
    assert "not an Indian regulation" in out["note"]


def test_air_passes_at_or_above_threshold_and_uses_conditional_variant():
    rows = _group_rows(50, 100, 45, 100)  # 0.9
    out = m.adverse_impact_ratio(rows)
    assert out["favourable_approve"]["air"] == 0.9 and out["favourable_approve"]["flagged"] is False
    assert out["favourable_approve_or_conditional"]["air"] == 0.9


def test_air_single_group_zero_rate_and_no_groups_do_not_crash():
    single = m.adverse_impact_ratio([rec(gender="Male")] * 5)
    assert single["favourable_approve"]["status"] == "insufficient_groups"
    assert single["favourable_approve"]["air"] is None and single["favourable_approve"]["flagged"] is False
    zero = m.adverse_impact_ratio(_group_rows(0, 40, 0, 40))
    assert zero["favourable_approve"]["status"] == "undefined_zero_favourable_rate"
    assert m.adverse_impact_ratio([])["favourable_approve"]["air"] is None


def test_air_unknown_group_excluded_and_small_group_noted():
    rows = _group_rows(10, 10, 5, 10) + [rec("U", "APPROVE", gender=None)]
    out = m.adverse_impact_ratio(rows)
    assert out["groups"]["unknown"]["n"] == 1
    assert out["favourable_approve"]["air"] == 0.5
    assert set(out["small_groups"]) == {"Male", "Female"}


def test_air_custom_group_key_and_final_decision_source():
    rows = [{**rec(f"{g}{i}", "REJECT", "APPROVE" if i < n else "DENY"), "region": g}
            for g, n in (("N", 8), ("S", 4)) for i in range(10)]
    out = m.adverse_impact_ratio(rows, group_key="region", decision_source="decision")
    assert out["favourable_approve"]["air"] == 0.5


# ---- outcomes --------------------------------------------------------------
def test_outcome_report_unavailable_without_labels():
    out = m.outcome_report([rec(), rec()])
    assert out["available"] is False and "none are invented" in out["reason"]
    assert m.outcome_report([])["available"] is False


def test_outcome_report_on_toy_dataset():
    rows = [rec(f"T{i}", score=s, bad=y) for i, (s, y) in enumerate(TOY)]
    out = m.outcome_report(rows, edges=[80, 65, 50])
    assert out["available"] is True
    assert out["auc"] == 0.96 and out["gini"] == 0.92
    assert out["ks"] == 0.6 and out["ks_basis"] == "banded" and out["ks_exact"] == 0.8
    assert out["auc_status"] == "good" and out["ks_status"] == "good"
    assert m.outcome_report(rows)["ks_basis"] == "exact"
    assert any("Bad outcomes" in w for w in out["warnings"])  # only 5 bad


def test_outcome_report_single_class_warns():
    out = m.outcome_report([rec(score=70, bad=0), rec(score=60, bad=0)])
    assert out["available"] is True and out["auc"] is None
    assert any("one outcome class" in w for w in out["warnings"])


def test_bad_rate_monotonic_and_violation():
    rows = []
    for band, bads in (("Excellent", 0), ("Good", 1), ("Fair", 2), ("Poor", 3), ("Very Poor", 4)):
        rows += [rec(band=band, bad=1 if i < bads else 0) for i in range(5)]
    ok = m.bad_rate_by_group(rows, "credit_band", m.CREDIT_BAND_ORDER)
    assert ok["monotonic"] is True and ok["groups"]["Very Poor"]["bad_rate_pct"] == 80.0
    rows += [rec(band="Excellent", bad=1) for _ in range(5)]  # Excellent now 50% > Good 20%
    bad = m.bad_rate_by_group(rows, "credit_band", m.CREDIT_BAND_ORDER)
    assert bad["monotonic"] is False and bad["violations"][0]["from"] == "Excellent"


def test_bad_rate_by_tier_ignores_unlabelled_and_unknown_groups():
    rows = [rec(tier="low", bad=0), rec(tier="low", bad=None), rec(tier="weird", bad=1)]
    out = m.bad_rate_by_group(rows, "credit_risk_tier", m.RISK_TIER_ORDER)
    assert out["groups"]["low"]["n"] == 1 and "weird" in out["not_in_order"]
    assert out["groups"]["high"]["bad_rate_pct"] is None


def test_confidence_calibration_buckets():
    rows = [rec(credit="APPROVE", conf=0.95, bad=0) for _ in range(10)]          # 0.95 -> 100% correct
    rows += [rec(credit="REJECT", conf=0.40, bad=0) for _ in range(10)]           # 0.40 -> 0% correct
    rows += [rec(credit="CONDITIONAL", conf=0.60, bad=1)]                        # referral - excluded
    out = m.confidence_calibration(rows)
    by = {b["range"]: b for b in out["buckets"]}
    assert by["0.90-1.00"]["realised_correct"] == 1.0 and by["0.90-1.00"]["well_calibrated"] is True  # |0.95-1.0| <= 0.10
    assert by["0.30-0.50"]["realised_correct"] == 0.0 and by["0.30-0.50"]["well_calibrated"] is False
    assert by["0.50-0.70"]["n"] == 0 and by["0.50-0.70"]["well_calibrated"] is None


def test_confidence_calibration_marks_close_bucket_well_calibrated():
    rows = [rec(credit="APPROVE", conf=0.95, bad=0 if i < 9 else 1) for i in range(10)]  # 0.95 vs 0.90
    out = m.confidence_calibration(rows)
    assert [b for b in out["buckets"] if b["n"]][0]["well_calibrated"] is True


# ---- normalize_record / report --------------------------------------------
def test_normalize_record_flattens_view_row():
    row = {
        "id": "APP-9", "created_at": "2026-10-01T00:00:00Z", "gender": "Female",
        "field_overrides": {"d1": {"net_salary": 1}}, "outcome_bad": 1,
        "view": {"id": "APP-9", "agents": {"credit": {"risk_score": 71.5, "preliminary_decision": "APPROVE"},
                                           "decision": {"decision": "SUSPEND"}}},
    }
    r = m.normalize_record(row)
    assert r["application_id"] == "APP-9" and r["gender"] == "Female" and r["outcome_bad"] == 1
    assert r["credit_analysis"]["risk_score"] == 71.5 and r["decision"]["decision"] == "SUSPEND"


def test_normalize_record_json_string_view_and_flat_passthrough():
    import json
    row = {"id": "X", "view": json.dumps({"agents": {"credit": {"risk_score": 1}}})}
    assert m.normalize_record(row)["credit_analysis"]["risk_score"] == 1
    flat = rec("Z")
    assert m.normalize_record(flat) == flat
    assert len(m.normalize_records([flat, row])) == 2


def test_phase1_report_has_every_section_and_handles_empty_input():
    for records in ([], [rec(gender="Male"), rec(gender="Female", credit="REJECT", decision="DENY")]):
        out = m.phase1_report(records, constants=DEFAULTS)
        assert set(out) == {
            "n_applications", "bureau_source_mix", "flag_trigger_rates", "decision_distribution",
            "confidence_distribution", "agreement_matrix", "upstream_data_quality_rate", "adverse_impact_ratio",
        }


def test_load_confidence_constants_matches_live_config_keys():
    c = m.load_confidence_constants()
    assert set(c) == set(DEFAULTS)
