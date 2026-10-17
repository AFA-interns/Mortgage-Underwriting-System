"""Hand-computed checks for app.property_valuation.metrics - pure functions,
no agent/pipeline execution involved. Examples below are taken directly
from PROPERTY_VALUATION_METRICS.md so the module matches the source
document exactly."""
import pytest

from app.property_valuation.metrics import (
    absolute_percentage_error,
    coverage_rate,
    mdape,
    ppe_rate,
    valuation_accuracy_report,
)


def test_absolute_percentage_error_matches_worked_example():
    # Actual = 50 lakh, predicted = 46 lakh -> |46-50|/50*100 = 8%
    assert absolute_percentage_error(46, 50) == pytest.approx(8.0)


def test_absolute_percentage_error_rejects_zero_actual():
    with pytest.raises(ValueError):
        absolute_percentage_error(10, 0)


def test_ppe10_matches_worked_example():
    # 70 of 100 pairs have <=10% error -> PPE10 = 70%
    pairs = [(108, 100)] * 70 + [(150, 100)] * 30  # 8% error vs 50% error
    result = ppe_rate(pairs, 10)
    assert result["n"] == 100
    assert result["successes"] == 70
    assert result["rate_pct"] == 70.0


def test_ppe20_matches_worked_example():
    # 85 of 100 pairs have <=20% error -> PPE20 = 85%
    pairs = [(115, 100)] * 85 + [(150, 100)] * 15
    result = ppe_rate(pairs, 20)
    assert result["successes"] == 85
    assert result["rate_pct"] == 85.0


def test_ppe_rate_boundary_is_inclusive():
    # Exactly at the threshold counts as a success ("10% or less").
    assert ppe_rate([(110, 100)], 10)["successes"] == 1


def test_ppe_rate_empty_pairs():
    assert ppe_rate([], 10) == {"threshold_pct": 10, "n": 0, "successes": 0, "rate_pct": 0.0}


def test_mdape_matches_worked_example():
    # Errors 4%, 10%, 25%, 8%, 5% -> sorted 4,5,8,10,25 -> median 8%.
    pairs = [
        (104, 100),  # 4%
        (110, 100),  # 10%
        (125, 100),  # 25%
        (108, 100),  # 8%
        (105, 100),  # 5%
    ]
    assert mdape(pairs) == {"n": 5, "mdape_pct": 8.0}


def test_mdape_empty_pairs():
    assert mdape([]) == {"n": 0, "mdape_pct": None}


def test_coverage_rate_matches_worked_example():
    # 700 of 1000 applications produced a valuation -> Coverage Rate = 70%.
    records = [{"estimated_value": 5_000_000.0, "value_source": "avnester"}] * 700
    records += [{"estimated_value": 0, "value_source": None}] * 300
    result = coverage_rate(records)
    assert result["total_applications"] == 1000
    assert result["valuations_produced"] == 700
    assert result["coverage_rate_pct"] == 70.0
    assert result["by_source"] == {"avnester": 700}
    assert result["no_valuation_count"] == 300


def test_coverage_rate_empty_is_zero_not_error():
    assert coverage_rate([]) == {
        "total_applications": 0, "valuations_produced": 0, "coverage_rate_pct": 0.0,
        "by_source": {}, "no_valuation_count": 0,
    }


def test_coverage_rate_treats_missing_or_null_estimated_value_as_no_valuation():
    records = [{"estimated_value": None, "value_source": None}, {"value_source": None}]
    result = coverage_rate(records)
    assert result["valuations_produced"] == 0
    assert result["no_valuation_count"] == 2


def test_valuation_accuracy_report_unavailable_without_labeled_pairs():
    # This system captures no actual transaction price anywhere today, so
    # this must report unavailable rather than fabricate a number.
    report = valuation_accuracy_report()
    assert report["available"] is False
    assert "actual transaction price" in report["reason"]


def test_valuation_accuracy_report_computes_when_pairs_are_supplied():
    pairs = [(104, 100), (110, 100), (125, 100), (108, 100), (105, 100)]
    report = valuation_accuracy_report(pairs)
    assert report["available"] is True
    assert report["n"] == 5
    assert report["mdape"]["mdape_pct"] == 8.0
    assert report["ppe10"]["rate_pct"] == pytest.approx(80.0)  # 4%,5%,8%,10% <=10% -> 4/5
    assert report["ppe20"]["rate_pct"] == pytest.approx(80.0)  # same 4/5 clear <=20% too (only 25% fails both)
