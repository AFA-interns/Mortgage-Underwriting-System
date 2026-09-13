"""Tests for the composite risk score, confidence, and the Credit Analysis
Agent's own preliminary decision rules."""
from app.credit.scoring import compute_confidence, compute_credit_risk_score, generate_preliminary_decision
from app.models.decision import CreditDecisionType


def test_decision_reject_on_two_severe_flags():
    decision = generate_preliminary_decision(
        cibil_score=700,
        credit_band="Good",
        foir=0.30,
        foir_threshold=0.55,
        red_flags=[
            "1 settled account(s) found in credit history",
            "DPD exceeding 90 days in last 12 months (max DPD: 120)",
        ],
    )
    assert decision == CreditDecisionType.REJECT


def test_decision_reject_on_foir_overshoot():
    decision = generate_preliminary_decision(
        cibil_score=720, credit_band="Good", foir=0.75, foir_threshold=0.45, red_flags=[],
    )
    assert decision == CreditDecisionType.REJECT


def test_decision_reject_on_low_cibil_without_compensating_factors():
    # foir_overshoot = 0.50 - 0.55 = -0.05, not under the -0.10 headroom
    # required for a compensating factor -> automatic reject.
    decision = generate_preliminary_decision(
        cibil_score=500, credit_band="Very Poor", foir=0.50, foir_threshold=0.55, red_flags=[],
    )
    assert decision == CreditDecisionType.REJECT


def test_decision_conditional_not_approve_on_low_cibil_with_compensating_factor():
    # Below the hard-reject threshold but comfortable FOIR headroom (-0.25)
    # and no red flags avoids an automatic reject - it must still land on
    # CONDITIONAL (manual review), never a clean APPROVE.
    decision = generate_preliminary_decision(
        cibil_score=500, credit_band="Very Poor", foir=0.30, foir_threshold=0.55, red_flags=[],
    )
    assert decision == CreditDecisionType.CONDITIONAL


def test_decision_conditional_on_new_to_credit():
    decision = generate_preliminary_decision(
        cibil_score=None, credit_band="New-to-Credit", foir=0.30, foir_threshold=0.55, red_flags=[],
    )
    assert decision == CreditDecisionType.CONDITIONAL


def test_decision_approve_clean_case():
    decision = generate_preliminary_decision(
        cibil_score=780, credit_band="Excellent", foir=0.30, foir_threshold=0.55, red_flags=[],
    )
    assert decision == CreditDecisionType.APPROVE


def test_confidence_lower_without_credit_history():
    with_history = compute_confidence(780, [])
    without_history = compute_confidence(None, [])
    assert without_history < with_history


def test_confidence_bounded_between_floor_and_one():
    score = compute_confidence(None, ["flag"] * 20)
    assert 0.0 <= score <= 1.0


def test_risk_score_within_bounds():
    score = compute_credit_risk_score("Excellent", 0.2, 0.55, [])
    assert 0 <= score <= 100


def test_risk_score_penalizes_red_flags():
    clean = compute_credit_risk_score("Good", 0.3, 0.55, [])
    flagged = compute_credit_risk_score(
        "Good", 0.3, 0.55, ["1 settled account(s) found in credit history"]
    )
    assert flagged < clean
