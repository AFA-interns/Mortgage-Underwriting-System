"""Audit service — append-only audit logging for decision records."""
from __future__ import annotations

from typing import Any

from app.models.decision import AuditRecord, DecisionResult


class AuditStore:
    """In-memory append-only audit store. Replace with PostgreSQL in production."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, audit: AuditRecord) -> None:
        self._records.append(audit.model_dump(mode="json"))

    def get_by_application(self, application_id: str) -> list[dict[str, Any]]:
        return [r for r in self._records if r.get("application_id") == application_id]

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._records)


# Global singleton — replace with dependency injection in production
audit_store = AuditStore()


def create_audit_record(
    application_id: str,
    validation: Any = None,
    contradictions: list[Any] | None = None,
    risk_assessment: Any = None,
    confidence_assessment: Any = None,
    crew_output: Any = None,
    final_decision: DecisionResult | None = None,
    errors: list[str] | None = None,
) -> AuditRecord:
    """Create and store an audit record."""
    human_review_required = bool(
        final_decision and final_decision.human_review_required
    )
    audit = AuditRecord(
        application_id=application_id,
        upstream_outputs={},
        validation=validation,
        contradictions=contradictions or [],
        risk_assessment=risk_assessment,
        confidence_assessment=confidence_assessment,
        crew_output=crew_output,
        final_decision=final_decision,
        rationale=final_decision.rationale if final_decision else "",
        human_review_status=(
            "REQUIRED" if human_review_required else "NOT_REQUIRED"
        ),
        errors=errors or [],
    )
    audit_store.record(audit)
    return audit
