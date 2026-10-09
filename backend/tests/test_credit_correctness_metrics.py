"""Correctness checks on the real credit_node (no outcome data needed).

Black-box: determinism, monotonicity of risk_score, and one test per ordered
branch of generate_preliminary_decision so branch coverage can be measured:

    pytest tests/test_credit_*.py --cov=app.credit --cov-branch --cov-report=term-missing

Bureau data is always pinned through state["credit_bureau_data"], so nothing
here depends on the simulated bureau stub.
"""
import re

import pytest

from app.credit.scoring import generate_preliminary_decision
from app.graph.nodes.credit import credit_node
from app.models.decision import CreditDecisionType as D
from tests.test_credit_node import _state  # reuse the existing borrower fixture builder

CLEAN_BUREAU = {
    "cibil_score": 780,
    "settled_accounts": 0,
    "written_off_accounts": 0,
    "max_dpd_last_12_months": 0,
    "recent_enquiries_last_90_days": 0,
    "credit_card_outstanding_total": 0,
    "source": "bureau",
}

_TIMESTAMPISH = re.compile(r"(time|_at$|^at$|date|created|updated)", re.I)


def _strip_timestamps(obj):
    if isinstance(obj, dict):
        return {k: _strip_timestamps(v) for k, v in obj.items() if not _TIMESTAMPISH.search(k)}
    if isinstance(obj, list):
        return [_strip_timestamps(v) for v in obj]
    return obj


def _run(bureau=None, **borrower):
    state = _state(borrower_overrides=borrower, credit_bureau_data={**CLEAN_BUREAU, **(bureau or {})})
    return credit_node(state)["credit_analysis"]


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------
def test_credit_node_is_deterministic_over_20_runs():
    bureau = {"cibil_score": 712, "settled_accounts": 1, "recent_enquiries_last_90_days": 4,
              "credit_card_outstanding_total": 40000}
    first = _strip_timestamps(_run(bureau))
    for _ in range(19):
        assert _strip_timestamps(_run(bureau)) == first


# --------------------------------------------------------------------------
# Monotonicity (credit_node only, everything else held fixed)
# --------------------------------------------------------------------------
def test_risk_score_non_decreasing_as_cibil_rises():
    scores = [_run({"cibil_score": c})["risk_score"] for c in range(300, 901, 10)]
    assert all(b >= a for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] > scores[0]  # the sweep must actually move the score


def test_risk_score_non_increasing_as_existing_debt_rises():
    scores = [_run(existing_debt=d)["risk_score"] for d in range(0, 120001, 5000)]
    assert all(b <= a for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_each_severe_red_flag_strictly_lowers_risk_score():
    stages = [
        {},
        {"settled_accounts": 1},
        {"settled_accounts": 1, "written_off_accounts": 1},
        {"settled_accounts": 1, "written_off_accounts": 1, "max_dpd_last_12_months": 120},
    ]
    results = [_run(s) for s in stages]
    scores = [r["risk_score"] for r in results]
    assert [len(r["flags"]) for r in results] == [0, 1, 2, 3]
    assert all(b < a for a, b in zip(scores, scores[1:])), scores


def test_one_severe_flag_costs_about_six_total_points_not_thirty():
    # red-flag component drops 30 (credit_config.yaml risk_score.red_flag_penalty.severe)
    # but carries weight 0.20 of risk_score -> 30 * 0.20 = 6 points overall.
    clean = _run()["risk_score"]
    flagged = _run({"settled_accounts": 1})["risk_score"]
    assert clean - flagged == pytest.approx(6.0, abs=0.02)


def test_new_to_credit_does_not_crash_and_gives_valid_decision():
    ca = _run({"cibil_score": None})
    assert ca["credit_band"] == "New-to-Credit"
    assert ca["cibil_score"] is None
    assert ca["preliminary_decision"] in {d.value for d in D}
    assert 0.0 <= ca["risk_score"] <= 100.0
    assert ca["confidence"] == pytest.approx(0.60)  # 0.90 - 0.30, no flags


# --------------------------------------------------------------------------
# One test per ordered branch of generate_preliminary_decision
# (8 return points: 3 REJECT, 4 CONDITIONAL, 1 default APPROVE)
# --------------------------------------------------------------------------
SEVERE_A = "1 settled account(s) found in credit history"
SEVERE_B = "DPD exceeding 90 days in last 12 months (max DPD: 120)"
MILD = "Possible loan stacking - 4 credit enquiries in last 90 days"


def _decide(cibil=780, band="Excellent", foir=0.30, thr=0.55, flags=()):
    return generate_preliminary_decision(cibil, band, foir, thr, list(flags))


def test_branch_1_low_cibil_without_compensating_factor_rejects():
    assert _decide(cibil=500, band="Very Poor", foir=0.50) is D.REJECT  # headroom only 0.05
    # compensating FOIR but a red flag present -> still reject
    assert _decide(cibil=500, band="Very Poor", foir=0.30, flags=[MILD]) is D.REJECT


def test_branch_2_foir_overshoot_beyond_reject_band_rejects():
    assert _decide(foir=0.71) is D.REJECT  # 0.55 + 0.15 = 0.70 boundary exceeded
    assert _decide(foir=0.70) is D.CONDITIONAL  # exactly at the boundary is not past it


def test_branch_3_two_severe_flags_rejects():
    assert _decide(flags=[SEVERE_A, SEVERE_B]) is D.REJECT


def test_branch_4_low_cibil_with_compensating_factor_is_conditional():
    assert _decide(cibil=500, band="Very Poor", foir=0.30) is D.CONDITIONAL


def test_branch_5_foir_over_threshold_but_inside_reject_band_is_conditional():
    assert _decide(foir=0.60) is D.CONDITIONAL


def test_branch_6_single_red_flag_is_conditional():
    assert _decide(flags=[MILD]) is D.CONDITIONAL
    assert _decide(flags=[SEVERE_A]) is D.CONDITIONAL  # one severe is not enough to reject


def test_branch_7_new_to_credit_is_conditional():
    assert _decide(cibil=None, band="New-to-Credit") is D.CONDITIONAL


def test_branch_8_clean_case_approves():
    assert _decide() is D.APPROVE


def test_branch_precedence_reject_wins_over_conditional_signals():
    # low CIBIL + two severe flags + FOIR over threshold: the reject checks run first
    assert _decide(cibil=500, band="Very Poor", foir=0.60, flags=[SEVERE_A, SEVERE_B]) is D.REJECT
    # FOIR in the reject band beats a clean everything-else profile
    assert _decide(cibil=None, band="New-to-Credit", foir=0.80) is D.REJECT


def test_risk_score_zero_foir_threshold_gives_zero_foir_component():
    from app.credit.scoring import compute_credit_risk_score

    # Excellent band 100*0.45 + foir 0*0.35 + no flags 100*0.20 = 65
    assert compute_credit_risk_score("Excellent", 0.30, 0.0, []) == pytest.approx(65.0)
