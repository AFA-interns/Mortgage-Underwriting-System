"""Human-in-the-loop review: see what each document extracted, correct a
field, and re-run the pipeline with that correction applied."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.document_ingestion.field_overrides import apply_overrides, validate_overrides
from app.models.document_ingestion import DocumentType, PANCardData
from app.main import app

client = TestClient(app)

# AVnester is a live external API; pin its result so property valuation (and
# therefore the risk score / decision) is identical on every run — tests
# that compare a decision across two runs must not depend on live data.
_STABLE_LISTINGS = {"listings": [
    {"listingId": f"id-{i}", "title": "t", "locality": "X", "price": 3_125_000, "carpetAreaSqft": 1000}
    for i in range(5)
]}


def _run_clean_demo() -> dict:
    with patch("app.tools.external_api.search_properties", return_value=_STABLE_LISTINGS):
        r = client.post("/api/v1/underwriting/run", data={"demo_scenario": "clean"})
    assert r.status_code == 200, r.text
    return r.json()


def _rerun(application_id: str):
    with patch("app.tools.external_api.search_properties", return_value=_STABLE_LISTINGS):
        return client.post(f"/api/v1/applications/{application_id}/rerun")


def _pan_doc(view: dict) -> dict:
    return next(d for d in view["document_files"] if d["type"] == "PAN_CARD")


# --------------------------------------------------------- field_overrides

def test_validate_overrides_rejects_unknown_field():
    bad = validate_overrides(DocumentType.PAN_CARD, {"not_a_field": "x"})
    assert "not_a_field" in bad


def test_validate_overrides_accepts_whitelisted_field():
    assert validate_overrides(DocumentType.PAN_CARD, {"pan_number": "ABCPS1234F"}) == {}


def test_apply_overrides_patches_entity_and_marks_provenance():
    entity = PANCardData(pan_number="WRONG00000X", full_name="Typo Name")
    applied = apply_overrides(entity, {"pan_number": "ABCPS1234F"})
    assert applied == ["pan_number"]
    assert entity.pan_number == "ABCPS1234F"
    assert entity.full_name == "Typo Name"  # untouched field is unaffected


def test_apply_overrides_skips_fields_not_on_the_model():
    entity = PANCardData(pan_number="ABCPS1234F")
    assert apply_overrides(entity, {"nonexistent": "x"}) == []
    assert entity.pan_number == "ABCPS1234F"


# ----------------------------------------------------------------- GET/PUT

def test_get_parsed_fields_for_a_document():
    view = _run_clean_demo()
    doc = _pan_doc(view)
    res = client.get(f"/api/v1/applications/{view['id']}/documents/{doc['id']}/parsed")
    assert res.status_code == 200
    body = res.json()
    assert body["doc_type"] == "PAN_CARD"
    assert body["extracted_fields"]["pan_number"] == "ABCPS1234F"
    assert body["overrides"] == {}
    assert set(body["editable_fields"]) == {"pan_number", "full_name", "father_name", "dob"}


def test_get_parsed_fields_404_for_unknown_application():
    res = client.get("/api/v1/applications/NOPE/documents/also-nope/parsed")
    assert res.status_code == 404


def test_get_parsed_fields_404_for_unknown_document():
    view = _run_clean_demo()
    res = client.get(f"/api/v1/applications/{view['id']}/documents/does-not-exist/parsed")
    assert res.status_code == 404


def test_put_overrides_rejects_unknown_field():
    view = _run_clean_demo()
    doc = _pan_doc(view)
    res = client.put(
        f"/api/v1/applications/{view['id']}/documents/{doc['id']}/parsed",
        json={"overrides": {"made_up_field": "x"}},
    )
    assert res.status_code == 400


def test_put_overrides_then_get_shows_effective_merge():
    view = _run_clean_demo()
    doc = _pan_doc(view)
    put = client.put(
        f"/api/v1/applications/{view['id']}/documents/{doc['id']}/parsed",
        json={"overrides": {"full_name": "Corrected Name"}},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["overrides"] == {"full_name": "Corrected Name"}
    assert body["effective_fields"]["full_name"] == "Corrected Name"
    assert body["effective_fields"]["pan_number"] == "ABCPS1234F"  # unedited field survives the merge


# ----------------------------------------------------------------- /rerun

def test_rerun_404_for_unknown_application():
    assert client.post("/api/v1/applications/NOPE/rerun").status_code == 404


def test_rerun_without_overrides_reproduces_the_decision():
    view = _run_clean_demo()
    rerun = _rerun(view["id"])
    assert rerun.status_code == 200
    body = rerun.json()
    assert body["id"] == view["id"]
    assert body["rerun_count"] == 1
    assert body["decision"]["decision"] == view["decision"]["decision"]


def test_rerun_keeps_the_same_id_across_multiple_reruns():
    """A correction must never spawn a second application for one case —
    the application id stays constant no matter how many times it's
    rerun, with rerun_count tracking how many corrections were applied."""
    view = _run_clean_demo()
    assert view.get("rerun_count", 0) == 0

    first = _rerun(view["id"]).json()
    assert first["id"] == view["id"]
    assert first["rerun_count"] == 1

    second = _rerun(view["id"]).json()
    assert second["id"] == view["id"]
    assert second["rerun_count"] == 2


def test_rerun_clears_the_previous_runs_documents():
    """Reusing the same application id must not accumulate every prior
    run's documents underneath it — only the latest run's documents
    should be stored and listed."""
    from app.services.applications import store

    view = _run_clean_demo()
    old_doc_ids = {d["id"] for d in view["document_files"]}

    rerun = _rerun(view["id"]).json()
    new_doc_ids = {d["id"] for d in rerun["document_files"]}

    assert len(new_doc_ids) == len(old_doc_ids)
    assert new_doc_ids.isdisjoint(old_doc_ids)
    for old_id in old_doc_ids:
        assert store.get_document(view["id"], old_id) is None


def test_an_invalid_override_flips_a_clean_approval_to_suspend():
    """Proves the override is actually applied before validation, not
    just stored: a syntactically invalid PAN must fail PAN validation on
    rerun exactly as it would if extraction had produced it originally."""
    view = _run_clean_demo()
    assert view["decision"]["decision"] == "APPROVE"
    doc = _pan_doc(view)

    client.put(
        f"/api/v1/applications/{view['id']}/documents/{doc['id']}/parsed",
        json={"overrides": {"pan_number": "NOT-A-VALID-PAN"}},
    )
    rerun = _rerun(view["id"]).json()
    assert rerun["decision"]["decision"] != "APPROVE"


def test_correctable_pan_error_demo_scenario_approves_after_fix():
    """The dedicated demo scenario for showing document correction live:
    baseline run is blocked by a malformed PAN number; correcting just
    that field and rerunning approves it."""
    with patch("app.tools.external_api.search_properties", return_value=_STABLE_LISTINGS):
        r = client.post("/api/v1/underwriting/run", data={"demo_scenario": "correctable_pan_error"})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["decision"]["decision"] != "APPROVE"

    doc = _pan_doc(view)
    put = client.put(
        f"/api/v1/applications/{view['id']}/documents/{doc['id']}/parsed",
        json={"overrides": {"pan_number": "ABCPS1234F"}},
    )
    assert put.status_code == 200

    rerun = _rerun(view["id"]).json()
    assert rerun["decision"]["decision"] == "APPROVE"


def test_rerun_persists_the_original_bureau_data_unchanged():
    """A rerun should isolate the document correction - it must not also
    silently roll a new simulated credit score under a new application id."""
    view = _run_clean_demo()
    rerun = _rerun(view["id"]).json()
    assert rerun["agents"]["credit"]["cibil_score"] == view["agents"]["credit"]["cibil_score"]


def test_rerun_on_application_with_no_stored_documents_is_rejected():
    import app.services.applications as applications_module

    app_id = applications_module.store.next_id()
    applications_module.store.save({
        "id": app_id, "borrower": "No Docs", "status": "Needs Review", "source": "test",
        "processing_seconds": 0.1, "created_at": "2026-01-01T00:00:00+00:00",
        "decision": {}, "document_files": [], "review_items": [],
    })
    res = client.post(f"/api/v1/applications/{app_id}/rerun")
    assert res.status_code == 400
