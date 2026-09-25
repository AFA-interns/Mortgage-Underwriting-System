"""Stored source documents (in-memory store) and the PostgreSQL store."""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_uploaded_documents_are_stored_and_downloadable(mock_docs):
    client = TestClient(app)
    run = client.post("/api/v1/underwriting/run", data={"demo_scenario": "missing_docs"})
    assert run.status_code == 200
    view = run.json()
    assert len(view["document_files"]) == 2
    assert all(not d["type"].startswith("DocumentType.") for d in view["document_files"])

    doc = view["document_files"][0]
    res = client.get(f"/api/v1/applications/{view['id']}/documents/{doc['id']}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert len(res.content) == doc["size_bytes"]


def test_document_is_scoped_to_its_application(mock_docs):
    client = TestClient(app)
    a = client.post("/api/v1/underwriting/run", data={"demo_scenario": "missing_docs"}).json()
    b = client.post("/api/v1/underwriting/run", data={"demo_scenario": "missing_docs"}).json()
    doc_of_a = a["document_files"][0]["id"]
    assert client.get(f"/api/v1/applications/{b['id']}/documents/{doc_of_a}").status_code == 404
    assert client.get(f"/api/v1/applications/{a['id']}/documents/nope").status_code == 404


def test_rejects_non_pdf_upload():
    r = TestClient(app).post(
        "/api/v1/underwriting/run",
        data={"name": "X", "monthly_income": "1", "loan_amount": "1"},
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert r.status_code == 400


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to run against PostgreSQL")
def test_postgres_store_round_trip():
    from app.services.db import PostgresApplicationStore

    store = PostgresApplicationStore(os.environ["TEST_DATABASE_URL"])
    app_id = store.next_id()
    view = {
        "id": app_id, "borrower": "T", "status": "Needs Review", "source": "test",
        "processing_seconds": 0.1, "created_at": "2026-01-01T00:00:00+00:00",
        "decision": {"decision": "SUSPEND", "risk_score": 50.0, "confidence": 0.5},
        "review_items": [{"id": f"RV-{app_id}-1", "application_id": app_id, "title": "t",
                          "severity": "High", "owner": "o", "evidence": "e", "status": "Open"}],
    }
    store.save(view)
    store.save_documents(app_id, [{"id": "d" * 32, "filename": "a.pdf", "type": "PAN_CARD", "content": b"%PDF-1"}])

    assert store.get(app_id)["borrower"] == "T"
    assert store.get_document(app_id, "d" * 32) == ("a.pdf", b"%PDF-1")
    assert store.resolve_review_item(f"RV-{app_id}-1")["status"] == "Resolved"
    assert store.get(app_id)["review_items"][0]["status"] == "Resolved"
