"""Evaluation metrics for the Property Valuation Agent - pure functions,
standard library only. Nothing here is imported by the agent itself, so it
can never change a valuation.

Two families, per PROPERTY_VALUATION_METRICS.md:

1. Coverage Rate - needs only what this system already stores (did the
   agent produce a valuation at all?). Runnable today.
2. PPE10 / PPE20 / MdAPE - need the ACTUAL transaction price per property to
   compare the valuation against. This system captures no such field
   anywhere (no closed-sale/outcome price on any application), so
   `valuation_accuracy_report()` always reports unavailable today rather
   than fabricate a number - same pattern as app.credit.metrics.outcome_report.

FSD (Forecast Standard Deviation) is deliberately not implemented: the
source document is explicit that FSD must reflect the model's own
uncertainty methodology, not be treated as the stdev of raw errors - and
this agent's comparable-median valuation isn't a calibrated probabilistic
model, so there is no honest number to compute here.
"""
from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Sequence

PPE_THRESHOLDS = (10, 20)


def absolute_percentage_error(predicted: float, actual: float) -> float:
    """|Predicted - Actual| / Actual * 100. `actual` must be > 0 (a real
    transaction price is never zero)."""
    if actual <= 0:
        raise ValueError("actual transaction price must be > 0")
    return abs(predicted - actual) / actual * 100.0


def ppe_rate(pairs: Sequence[tuple[float, float]], threshold_pct: float) -> dict[str, Any]:
    """Percent of (predicted, actual) pairs within `threshold_pct`% of the
    actual price - PPE10 is ppe_rate(pairs, 10), PPE20 is ppe_rate(pairs, 20).
    """
    n = len(pairs)
    if n == 0:
        return {"threshold_pct": threshold_pct, "n": 0, "successes": 0, "rate_pct": 0.0}
    errors = [absolute_percentage_error(p, a) for p, a in pairs]
    successes = sum(1 for e in errors if e <= threshold_pct)
    return {
        "threshold_pct": threshold_pct,
        "n": n,
        "successes": successes,
        "rate_pct": round(100.0 * successes / n, 2),
    }


def mdape(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """Median Absolute Percentage Error across all (predicted, actual) pairs."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "mdape_pct": None}
    errors = [absolute_percentage_error(p, a) for p, a in pairs]
    return {"n": n, "mdape_pct": round(statistics.median(errors), 2)}


def coverage_rate(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Of all property-valuation attempts, what share actually produced a
    valuation (`estimated_value > 0`), and from which source
    (avnester / scraped_db / local_db / none)? Needs no ground truth -
    only whether the agent itself succeeded.

    Each record: {"estimated_value": float, "value_source": str | None}.
    """
    total = len(records)
    if total == 0:
        return {
            "total_applications": 0, "valuations_produced": 0, "coverage_rate_pct": 0.0,
            "by_source": {}, "no_valuation_count": 0,
        }
    produced = [r for r in records if (r.get("estimated_value") or 0) > 0]
    by_source = Counter(r.get("value_source") or "none" for r in produced)
    return {
        "total_applications": total,
        "valuations_produced": len(produced),
        "coverage_rate_pct": round(100.0 * len(produced) / total, 2),
        "by_source": dict(by_source),
        "no_valuation_count": total - len(produced),
    }


def valuation_accuracy_report(pairs: Sequence[tuple[float, float]] | None = None) -> dict[str, Any]:
    """PPE10/PPE20/MdAPE against labeled (predicted, actual_transaction_price)
    pairs. Returns {"available": False, "reason": ...} - and never a
    fabricated number - when no pairs are supplied, which is the honest
    state of this system today: see module docstring.
    """
    if not pairs:
        return {
            "available": False,
            "reason": (
                "No actual transaction price is captured anywhere in this "
                "system for any property - PPE10/PPE20/MdAPE need the real "
                "selling price to compare the valuation against, not just the "
                "valuation itself. See PROPERTY_VALUATION_METRICS.md, "
                "'What this system would need to capture'."
            ),
        }
    return {
        "available": True,
        "n": len(pairs),
        "ppe10": ppe_rate(pairs, 10),
        "ppe20": ppe_rate(pairs, 20),
        "mdape": mdape(pairs),
    }
