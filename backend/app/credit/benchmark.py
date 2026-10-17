"""Credit Agent Phase 1 metrics (see CREDIT_METRICS.md) computed directly
from applications already stored by this server - no manual psql export
needed. Phase 1 deliberately needs no outcome labels (bureau source mix,
red-flag trigger rates, decision distribution, confidence-formula checks,
Credit vs Decision agreement, upstream data-quality rate, adverse impact
ratio), unlike Phase 2 (drift, needs two saved batches) and Phase 3 (needs
closed-loan outcomes this system does not capture yet - see
scripts/credit_metrics_report.py for the offline, label-aware CLI).

Shared by the /api/v1/metrics/credit endpoint (frontend "run metrics" button).
"""
from __future__ import annotations

from typing import Any

from app.credit import metrics as m


def _gender_for(store: Any, app_id: str, document_files: list[dict[str, Any]]) -> str | None:
    """Gender lives only in the Aadhaar document's parsed fields, never in
    the application view itself (it is an audit attribute, not a model
    input - see CREDIT_METRICS.md's adverse-impact-ratio note)."""
    aadhaar = next((d for d in document_files if d.get("type") == "AADHAAR_CARD" and d.get("has_parsed_fields")), None)
    if aadhaar is None:
        return None
    parsed = store.get_parsed_fields(app_id, aadhaar["id"])
    if not parsed:
        return None
    return (parsed.get("fields") or {}).get("gender")


def _field_overrides_for(store: Any, app_id: str, document_files: list[dict[str, Any]]) -> dict[str, Any] | None:
    reviewable = [d for d in document_files if d.get("has_parsed_fields")]
    if not reviewable:
        return None  # "no review data supplied" (distinct from {} = reviewable, nothing changed)
    return {d["id"]: (store.get_override(app_id, d["id"]) or {}) for d in reviewable}


def _build_records() -> list[dict[str, Any]]:
    from app.services.applications import store

    records: list[dict[str, Any]] = []
    for view in store.list():
        app_id = view["id"]
        document_files = view.get("document_files") or []
        agents = view.get("agents") or {}
        records.append({
            "application_id": app_id,
            "created_at": view.get("created_at"),
            "credit_analysis": agents.get("credit") or {},
            "decision": view.get("decision") or agents.get("decision") or {},
            "gender": _gender_for(store, app_id, document_files),
            "field_overrides": _field_overrides_for(store, app_id, document_files),
            "outcome_bad": None,  # not captured anywhere yet - see CREDIT_METRICS.md Phase 3
        })
    return records


def run_phase1_report() -> dict[str, Any]:
    """Runs CREDIT_METRICS.md's Phase 1 report against every application
    this server currently has stored. Returns {"available": False, "reason":
    ...} instead of an empty/misleading report when there's nothing to
    measure yet.
    """
    records = _build_records()
    if not records:
        return {
            "available": False,
            "reason": "No applications stored yet - run or import at least one application first.",
        }

    report = m.phase1_report(
        records,
        group_key="gender",
        expected_flags=m.EXPECTED_FLAGS,
        constants=m.load_confidence_constants(),
    )
    report["available"] = True
    return report
