"""Runs the Property Valuation Agent's Coverage Rate metric live against
every application this server currently has stored - no manual export,
no ground truth needed (see app.property_valuation.metrics). PPE10/PPE20/
MdAPE stay reported as unavailable: see valuation_accuracy_report().

Shared by the /api/v1/metrics/property endpoint (frontend "run metrics"
button).
"""
from __future__ import annotations

from typing import Any

from app.property_valuation import metrics as m


def _build_records() -> list[dict[str, Any]]:
    from app.services.applications import store

    records: list[dict[str, Any]] = []
    for view in store.list():
        prop = (view.get("agents") or {}).get("property") or {}
        records.append({
            "application_id": view.get("id"),
            "estimated_value": prop.get("estimated_value"),
            "value_source": next(
                (e.get("source") for e in (prop.get("evidence") or []) if e.get("field") == "estimated_value"),
                None,
            ),
        })
    return records


def run_coverage_report() -> dict[str, Any]:
    """Coverage Rate over every stored application, plus the (always
    unavailable today) accuracy report, so the frontend can show both in
    one call and explain why only one of them has a number.
    """
    records = _build_records()
    if not records:
        return {
            "available": False,
            "reason": "No applications stored yet - run or import at least one application first.",
        }

    coverage = m.coverage_rate(records)
    coverage["available"] = True
    coverage["accuracy"] = m.valuation_accuracy_report(None)
    return coverage
