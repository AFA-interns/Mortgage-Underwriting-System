from app.compliance.flags import RuleFlag
from app.compliance.scoring import compute_confidence
from app.models.decision import Severity

CONFIG = {
    "confidence": {
        "base": 0.90,
        "critical_flag_penalty": 0.15,
        "warning_flag_penalty": 0.05,
        "floor": 0.30,
    }
}


def test_no_flags_gives_base_confidence():
    assert compute_confidence([], CONFIG) == 0.90


def test_one_critical_flag_docks_penalty():
    flags = [RuleFlag(code="X", severity=Severity.CRITICAL, message="m")]
    assert compute_confidence(flags, CONFIG) == 0.75


def test_one_warning_flag_docks_smaller_penalty():
    flags = [RuleFlag(code="X", severity=Severity.MEDIUM, message="m")]
    assert compute_confidence(flags, CONFIG) == 0.85


def test_score_never_goes_below_floor():
    flags = [RuleFlag(code="X", severity=Severity.CRITICAL, message="m") for _ in range(10)]
    assert compute_confidence(flags, CONFIG) == 0.30


def test_score_never_exceeds_one():
    config = {**CONFIG, "confidence": {**CONFIG["confidence"], "base": 1.5}}
    assert compute_confidence([], config) == 1.0


def test_low_severity_flags_do_not_count_as_warnings():
    # LOW severity (e.g. NHB informational flag) shouldn't dock confidence -
    # only MEDIUM/HIGH (warning-level) and CRITICAL do.
    flags = [RuleFlag(code="X", severity=Severity.LOW, message="m")]
    assert compute_confidence(flags, CONFIG) == 0.90
