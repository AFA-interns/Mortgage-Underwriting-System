"""PostgreSQL persistence for applications and the human-review queue.

Selected at startup from DATABASE_URL (see app.services.applications). The full
UI view of each application is stored as JSONB so the API returns exactly what
the pipeline produced; review items live in their own table because they are
edited after the fact.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, LargeBinary, Sequence, String, Text, create_engine, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass


# Registered on the metadata so create_all() creates it.
application_seq = Sequence("application_seq", metadata=Base.metadata)


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    borrower: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str | None] = mapped_column(String(16))
    risk_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    processing_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    view: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ReviewItemRow(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(16))
    owner: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="Open")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentRow(Base):
    """An uploaded source document (PDF bytes), kept so a human reviewer can open it."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def normalise_url(raw: str) -> URL:
    """Accepts postgresql:// or the older postgresql+asyncpg:// and returns a
    psycopg (v3) SQLAlchemy URL."""
    url = make_url(raw.strip())
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"DATABASE_URL must be a PostgreSQL URL, got '{url.get_backend_name()}'")
    return url.set(drivername="postgresql+psycopg")


def ensure_database(url: URL) -> bool:
    """Creates the target database if it doesn't exist. Returns True if created."""
    name = url.database or ""
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsupported database name '{name}' (use letters, digits, underscore).")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
                return True
            return False
    finally:
        admin.dispose()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _item_dict(row: ReviewItemRow) -> dict[str, Any]:
    out = {
        "id": row.id,
        "application_id": row.application_id,
        "title": row.title,
        "severity": row.severity,
        "owner": row.owner,
        "evidence": row.evidence,
        "status": row.status,
    }
    if row.resolved_at:
        out["resolved_at"] = _iso(row.resolved_at)
    return out


class PostgresApplicationStore:
    kind = "postgres"

    def __init__(self, raw_url: str) -> None:
        url = normalise_url(raw_url)
        self.created_database = ensure_database(url)
        self.engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self._session = sessionmaker(self.engine, expire_on_commit=False)
        self.description = f"{url.host}:{url.port or 5432}/{url.database}"

    def next_id(self) -> str:
        with self.engine.begin() as conn:
            n = conn.execute(select(application_seq.next_value())).scalar_one()
        return f"LN-{datetime.now(UTC).year}-{n:04d}"

    def save(self, view: dict[str, Any]) -> None:
        decision = view.get("decision") or {}
        with self._session.begin() as s:
            s.merge(ApplicationRow(
                id=view["id"],
                borrower=view["borrower"],
                status=view["status"],
                decision=decision.get("decision"),
                risk_score=decision.get("risk_score"),
                confidence=decision.get("confidence"),
                source=view.get("source", ""),
                processing_seconds=view.get("processing_seconds", 0.0),
                created_at=datetime.fromisoformat(view["created_at"]),
                view=view,
            ))
            s.flush()
            for pos, item in enumerate(view.get("review_items", [])):
                s.merge(ReviewItemRow(
                    id=item["id"], application_id=view["id"], position=pos, title=item["title"],
                    severity=item["severity"], owner=item["owner"], evidence=item["evidence"],
                    status=item.get("status", "Open"),
                ))

    def _hydrate(self, s: Session, row: ApplicationRow) -> dict[str, Any]:
        view = dict(row.view)
        items = s.scalars(
            select(ReviewItemRow).where(ReviewItemRow.application_id == row.id).order_by(ReviewItemRow.position)
        ).all()
        view["review_items"] = [_item_dict(i) for i in items]
        return view

    def get(self, application_id: str) -> dict[str, Any] | None:
        with self._session() as s:
            row = s.get(ApplicationRow, application_id)
            return self._hydrate(s, row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self._session() as s:
            rows = s.scalars(select(ApplicationRow).order_by(ApplicationRow.created_at.desc())).all()
            return [self._hydrate(s, r) for r in rows]

    def review_items(self) -> list[dict[str, Any]]:
        with self._session() as s:
            rows = s.execute(
                select(ReviewItemRow)
                .join(ApplicationRow, ApplicationRow.id == ReviewItemRow.application_id)
                .order_by(ApplicationRow.created_at.desc(), ReviewItemRow.position)
            ).scalars().all()
            return [_item_dict(r) for r in rows]

    def resolve_review_item(self, item_id: str) -> dict[str, Any] | None:
        with self._session.begin() as s:
            row = s.get(ReviewItemRow, item_id)
            if row is None:
                return None
            row.status = "Resolved"
            row.resolved_at = datetime.now(UTC)
            return _item_dict(row)

    def save_documents(self, application_id: str, docs: list[dict[str, Any]]) -> None:
        now = datetime.now(UTC)
        with self._session.begin() as s:
            for d in docs:
                s.add(DocumentRow(
                    id=d["id"], application_id=application_id, filename=d["filename"],
                    doc_type=d["type"], size_bytes=len(d["content"]), content=d["content"], uploaded_at=now,
                ))

    def get_document(self, application_id: str, doc_id: str) -> tuple[str, bytes] | None:
        with self._session() as s:
            row = s.get(DocumentRow, doc_id)
            if row is None or row.application_id != application_id:
                return None
            return row.filename, bytes(row.content)
