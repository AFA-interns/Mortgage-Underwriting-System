"""Application service: runs the full underwriting graph and keeps the results
(in memory) so the frontend can list applications, open their agent reports
and work the human-review queue.

`build_view` turns the raw LangGraph state into one JSON-safe document; the
frontend renders only from that view and never re-derives decisions.
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.graph.workflow import build_underwriting_graph

logger = logging.getLogger(__name__)

# Synthetic bureau data + borrower for each demo scenario. The stub bureau
# derives a score from the application id, so demos pin explicit bureau data
# to stay deterministic (credit_node accepts state["credit_bureau_data"]).
_CLEAN_BUREAU = {
    "cibil_score": 785, "settled_accounts": 0, "written_off_accounts": 0,
    "max_dpd_last_12_months": 0, "recent_enquiries_last_90_days": 1,
    "credit_card_outstanding_total": 20000.0, "oldest_account_age_months": 96,
}

DEMO_SCENARIOS: dict[str, dict[str, Any]] = {
    "clean": {
        "label": "Clean prime borrower",
        "description": "Salaried TCS employee, full KYC + income pack, Coimbatore residential plot.",
        "key": "clean_prime",
        "profile": {
            "name": "Aarav Sharma", "monthly_income": 150000, "employment_type": "Salaried",
            "loan_amount": 5_000_000, "loan_tenure_months": 240,
            "property_value": 7_500_000, "existing_debt": 15000,
        },
        "bureau": _CLEAN_BUREAU,
    },
    "name_mismatch": {
        "label": "Name discrepancy",
        "description": "PAN, Aadhaar and payslip carry different spellings of the name.",
        "key": "name_discrepancy",
        "profile": {
            "name": "Priya Suresh Patel", "monthly_income": 110000, "employment_type": "Salaried",
            "loan_amount": 4_000_000, "loan_tenure_months": 240,
            "property_value": 6_000_000, "existing_debt": 0,
        },
        "bureau": {**_CLEAN_BUREAU, "cibil_score": 730},
    },
    "salary_mismatch": {
        "label": "Salary vs bank mismatch",
        "description": "Payslip net salary does not match the bank credit; no Aadhaar supplied.",
        "key": "salary_discrepancy",
        "profile": {
            "name": "Vikram Malhotra", "monthly_income": 160000, "employment_type": "Salaried",
            "loan_amount": 6_000_000, "loan_tenure_months": 240,
            "property_value": 9_000_000, "existing_debt": 10000,
        },
        "bureau": {**_CLEAN_BUREAU, "cibil_score": 700},
    },
    "missing_docs": {
        "label": "Missing documents",
        "description": "Only a PAN card and one payslip were provided.",
        "key": "missing_docs",
        "profile": {
            "name": "Rahul Verma", "monthly_income": 90000, "employment_type": "Salaried",
            "loan_amount": 3_500_000, "loan_tenure_months": 180,
            "property_value": 5_000_000, "existing_debt": 5000,
        },
        "bureau": {**_CLEAN_BUREAU, "cibil_score": 690},
    },
}


class ApplicationStore:
    """In-memory store: used when DATABASE_URL is unset or unreachable."""

    kind = "memory"
    description = "in-memory (data is lost on restart)"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._apps: dict[str, dict[str, Any]] = {}
        self._docs: dict[tuple[str, str], tuple[str, bytes]] = {}
        self._counter = 0

    def next_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"LN-{datetime.now(UTC).year}-{self._counter:04d}"

    def save(self, view: dict[str, Any]) -> None:
        with self._lock:
            self._apps[view["id"]] = view

    def get(self, application_id: str) -> dict[str, Any] | None:
        return self._apps.get(application_id)

    def save_documents(self, application_id: str, docs: list[dict[str, Any]]) -> None:
        with self._lock:
            for d in docs:
                self._docs[(application_id, d["id"])] = (d["filename"], d["content"])

    def get_document(self, application_id: str, doc_id: str) -> tuple[str, bytes] | None:
        return self._docs.get((application_id, doc_id))

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._apps.values(), key=lambda a: a["created_at"], reverse=True)

    def review_items(self) -> list[dict[str, Any]]:
        return [item for app in self.list() for item in app["review_items"]]

    def resolve_review_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            for app in self._apps.values():
                for item in app["review_items"]:
                    if item["id"] == item_id:
                        item["status"] = "Resolved"
                        item["resolved_at"] = datetime.now(UTC).isoformat()
                        return item
        return None


def _make_store() -> Any:
    """PostgreSQL when DATABASE_URL is set and reachable, otherwise memory.
    A failed connection is logged loudly and reported by /health."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return ApplicationStore()
    try:
        from app.services.db import PostgresApplicationStore

        pg = PostgresApplicationStore(url)
        logger.info("Application store: PostgreSQL %s%s", pg.description,
                    " (database created)" if pg.created_database else "")
        return pg
    except Exception as exc:  # bad credentials, server down, missing driver...
        logger.error("DATABASE_URL is set but PostgreSQL is unavailable, using memory: %s", exc)
        fallback = ApplicationStore()
        fallback.description = f"in-memory (PostgreSQL unavailable: {type(exc).__name__})"
        return fallback


store = _make_store()


def _pct(value: Any) -> str:
    return f"{float(value) * 100:.0f}%" if isinstance(value, (int, float)) else "—"


def _inr(value: Any) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "—"
    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f} Cr"
    if value >= 100_000:
        return f"₹{value / 100_000:.2f} L"
    return f"₹{value:,.0f}"


def _stages(state: dict[str, Any]) -> list[dict[str, Any]]:
    doc = state.get("document_analysis") or {}
    credit = state.get("credit_analysis") or {}
    prop = state.get("property_analysis") or {}
    comp = state.get("compliance_analysis") or {}
    dec = state.get("decision") or {}
    critical = comp.get("critical_flags") or []
    prop_ok = (prop.get("estimated_value") or 0) > 0

    return [
        {
            "name": "Document Ingestion",
            "confidence": doc.get("extraction_confidence"),
            "status": "Flagged" if doc.get("missing_documents") or doc.get("contradictions") else "Complete",
            "subtitle": f"{len(doc.get('documents') or [])} documents processed",
            "highlights": [
                f"Verification: {doc.get('verification_status', 'unknown')}",
                f"Missing: {', '.join(doc.get('missing_documents') or []) or 'none'}",
                f"Contradictions: {len(doc.get('contradictions') or [])}",
            ],
        },
        {
            "name": "Credit Analysis",
            "confidence": credit.get("confidence"),
            "status": "Complete" if credit else "Flagged",
            "subtitle": f"CIBIL {credit.get('cibil_score', '—')} · {credit.get('credit_band', '—')}",
            "highlights": [
                f"FOIR {_pct(credit.get('foir'))} · LTV {_pct(credit.get('ltv'))}",
                f"Preliminary decision: {credit.get('preliminary_decision', '—')}",
                f"Risk flags: {len(credit.get('flags') or [])}",
            ],
        },
        {
            "name": "Property Valuation",
            "confidence": prop.get("valuation_confidence"),
            "status": "Complete" if prop_ok else "Flagged",
            "subtitle": f"Estimated {_inr(prop.get('estimated_value'))}" if prop_ok else "No valuation available",
            "highlights": [
                f"Range {_inr(prop.get('market_range_low'))} – {_inr(prop.get('market_range_high'))}",
                f"{len(prop.get('comparables') or [])} live AVnester comparables",
            ] + list(prop.get("flags") or []),
        },
        {
            "name": "Compliance",
            "confidence": comp.get("confidence"),
            "status": "Hard gate" if critical else "Complete",
            "subtitle": f"{len(critical)} critical flag(s)" if critical else "All hard-gate checks passed",
            "highlights": [f"{k}: {v}" for k, v in (comp.get("rule_status") or {}).items()],
        },
        {
            "name": "Decision",
            "confidence": dec.get("confidence"),
            "status": "Complete" if dec.get("decision") != "SUSPEND" else "Flagged",
            "subtitle": f"{dec.get('decision', '—')} · risk {dec.get('risk_score', '—')}",
            "highlights": [dec.get("rationale", "")],
        },
    ]


def _review_items(app_id: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Derives the human-review queue from what the agents flagged."""
    items: list[tuple[str, str, str, str]] = []  # (title, severity, owner, evidence)
    comp = state.get("compliance_analysis") or {}
    doc = state.get("document_analysis") or {}
    prop = state.get("property_analysis") or {}
    dec = state.get("decision") or {}

    for flag in comp.get("critical_flags") or []:
        items.append(("Critical compliance flag", "High", "Compliance Agent", str(flag)))
    for c in doc.get("contradictions") or []:
        items.append(("Cross-document contradiction", "High" if c.get("severity") in ("HIGH", "CRITICAL") else "Medium",
                      "Document Agent", c.get("description", "")))
    if doc.get("missing_documents"):
        items.append(("Missing documents", "Medium", "Document Agent",
                      "Missing: " + ", ".join(doc["missing_documents"])))
    if (prop.get("estimated_value") or 0) <= 0:
        items.append(("Property valuation unavailable", "High", "Property Agent",
                      "; ".join(prop.get("flags") or ["No comparable listings were found."])))
    if dec.get("human_review_required") and not items:
        items.append(("Decision requires human review", "Medium", "Decision Agent", dec.get("rationale", "")))

    return [
        {
            "id": f"RV-{app_id}-{i + 1}",
            "application_id": app_id,
            "title": title,
            "severity": severity,
            "owner": owner,
            "evidence": evidence,
            "status": "Open",
        }
        for i, (title, severity, owner, evidence) in enumerate(items)
    ]


def build_view(
    app_id: str,
    state: dict[str, Any],
    profile: dict[str, Any],
    documents: list[str],
    started: float,
    source: str,
    document_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dec = state.get("decision") or {}
    report = state.get("underwriting_report") or {}
    prop = state.get("property_analysis") or {}
    doc_out = state.get("doc_ingestion_output") or {}
    prop_profile = doc_out.get("property_profile") or {}
    decision = dec.get("decision", "SUSPEND")
    status = {"APPROVE": "Approved", "DENY": "Declined"}.get(decision, "Needs Review")

    view = {
        "id": app_id,
        "borrower": profile.get("name") or "Unknown borrower",
        "created_at": datetime.now(UTC).isoformat(),
        "processing_seconds": round(time.time() - started, 1),
        "source": source,
        "documents": documents,
        "document_files": document_files or [],
        "status": status,
        "decision": dec,
        "loan": {
            "amount": profile.get("loan_amount"),
            "tenure_months": profile.get("loan_tenure_months"),
            "monthly_income": profile.get("monthly_income"),
            "existing_debt": profile.get("existing_debt"),
            "employment_type": profile.get("employment_type"),
            "declared_property_value": profile.get("property_value"),
        },
        "property_label": prop_profile.get("property_address") or prop_profile.get("locality") or "—",
        "property_type": prop_profile.get("property_type") or "—",
        "stages": _stages(state),
        "agents": {
            "document": state.get("document_analysis") or {},
            "credit": state.get("credit_analysis") or {},
            "property": prop,
            "compliance": state.get("compliance_analysis") or {},
            "decision": dec,
        },
        "report": report,
        "errors": [e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in state.get("errors", [])],
        "review_items": _review_items(app_id, state),
    }
    return _json_safe(view)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None  # JSON / JSONB cannot represent NaN or Infinity
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value") and not isinstance(obj, (str, int, float, bool)):
        return obj.value  # enums
    if hasattr(obj, "model_dump"):
        return _json_safe(obj.model_dump(mode="json"))
    return obj


def run_application(
    profile: dict[str, Any],
    file_paths: list[str],
    file_names: list[str],
    bureau: dict[str, Any] | None = None,
    source: str = "upload",
) -> dict[str, Any]:
    """Runs the full pipeline (ingestion -> credit/property/compliance -> decision)."""
    app_id = store.next_id()
    started = time.time()
    state: dict[str, Any] = {
        "application_id": app_id,
        "raw_document_paths": file_paths,
        "borrower_profile": profile,
        "errors": [],
    }
    if bureau:
        state["credit_bureau_data"] = bureau

    graph = build_underwriting_graph().compile()
    result = graph.invoke(state)

    # Keep the source PDFs so a human reviewer can open them later.
    type_by_name = {
        d.get("filename"): d.get("type", "UNKNOWN")
        for d in (result.get("document_analysis") or {}).get("documents", [])
    }
    stored: list[dict[str, Any]] = []
    for path, name in zip(file_paths, file_names):
        with open(path, "rb") as fh:
            content = fh.read()
        stored.append({
            "id": uuid.uuid4().hex,
            "filename": name,
            "type": str(getattr(t := type_by_name.get(os.path.basename(path), "UNKNOWN"), "value", t)),
            "content": content,
        })
    document_files = [
        {"id": d["id"], "filename": d["filename"], "type": d["type"], "size_bytes": len(d["content"])}
        for d in stored
    ]

    view = build_view(app_id, result, profile, file_names, started, source, document_files)
    store.save(view)
    store.save_documents(app_id, stored)
    return view
