"""Tests for JPG/PNG upload support: convert to PDF, OCR if there is no
text layer, and run through the normal document-ingestion pipeline."""
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

# AVnester is a live external API; pin its result for tests that assert a
# specific decision, so they don't depend on live data or network access.
_STABLE_LISTINGS = {"listings": [
    {"listingId": f"id-{i}", "title": "t", "locality": "X", "price": 3_125_000, "carpetAreaSqft": 1000}
    for i in range(5)
]}

from app.document_ingestion.image_to_pdf import convert_image_to_pdf
from app.document_ingestion.preprocessor import DocumentPreprocessor
from app.main import app
from app.services.ocr import ocr_available

requires_tesseract = pytest.mark.skipif(not ocr_available(), reason="Tesseract OCR is not installed")


def _pan_card_png(path: str) -> None:
    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 40), "INCOME TAX DEPARTMENT - GOVT. OF INDIA", fill="black")
    d.text((40, 100), "Permanent Account Number", fill="black")
    d.text((40, 140), "ABCPS1234F", fill="black")
    d.text((40, 180), "Name: Aarav Sharma", fill="black")
    d.text((40, 220), "Father's Name: Rakesh Sharma", fill="black")
    d.text((40, 260), "Date of Birth: 14/08/1990", fill="black")
    img.save(path)


def test_convert_image_to_pdf_produces_a_real_pdf():
    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "card.png")
        _pan_card_png(png_path)
        pdf_path = convert_image_to_pdf(png_path)
        assert pdf_path.endswith(".pdf")
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"


def test_convert_image_to_pdf_rejects_non_image():
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "notes.txt")
        with open(bad, "w") as f:
            f.write("hello")
        with pytest.raises(ValueError):
            convert_image_to_pdf(bad)


@requires_tesseract
def test_preprocessor_ocrs_a_converted_image_and_extracts_the_pan():
    from app.document_ingestion.classifier import DocumentClassifier
    from app.document_ingestion.extractors import DocumentExtractors

    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "pan_photo.png")
        _pan_card_png(png_path)

        prep = DocumentPreprocessor.process_file(png_path)
        assert prep.file_type == "PDF"
        assert prep.metadata["ocr_used"] is True
        assert len(prep.raw_text.strip()) > 10

        doc_type, conf = DocumentClassifier.classify(prep)
        assert doc_type.value == "PAN_CARD"
        assert conf >= 0.6

        pan = DocumentExtractors.extract_pan(prep)
        assert pan.full_name == "Aarav Sharma"


def test_blank_image_with_no_ocr_degrades_gracefully(monkeypatch):
    """Without OCR (or on a genuinely blank page) the document is still
    processed, just with no text — it does not crash the pipeline."""
    monkeypatch.setattr("app.document_ingestion.preprocessor.ocr_available", lambda: False)
    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "blank.png")
        Image.new("RGB", (400, 300), "white").save(png_path)
        prep = DocumentPreprocessor.process_file(png_path)
        assert prep.file_type == "PDF"
        assert prep.metadata["ocr_used"] is False
        assert prep.raw_text.strip() == ""


@requires_tesseract
def test_upload_endpoint_accepts_png_and_stores_it_as_pdf():
    os.environ.setdefault("DATABASE_URL", "")
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "pan_photo.png")
        _pan_card_png(png_path)
        with open(png_path, "rb") as f:
            res = client.post(
                "/api/v1/underwriting/run",
                data={"name": "Aarav Sharma", "monthly_income": "150000", "loan_amount": "5000000"},
                files=[("files", ("pan_photo.png", f, "image/png"))],
            )
    assert res.status_code == 200
    view = res.json()
    doc = view["document_files"][0]
    assert doc["filename"] == "pan_photo.pdf"
    assert doc["type"] == "PAN_CARD"

    dl = client.get(f"/api/v1/applications/{view['id']}/documents/{doc['id']}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF")


@requires_tesseract
def test_image_demo_scenario_is_listed():
    ids = [s["id"] for s in TestClient(app).get("/api/v1/demo-scenarios").json()]
    assert "image_upload" in ids


@requires_tesseract
def test_image_demo_scenario_converts_ocrs_and_approves():
    """End-to-end: the bundled PAN (PNG) and Aadhaar (JPG) photos convert,
    OCR cleanly, extract correctly, and the application reaches the same
    outcome as the equivalent all-PDF clean scenario."""
    client = TestClient(app)
    with patch("app.tools.external_api.search_properties", return_value=_STABLE_LISTINGS):
        res = client.post("/api/v1/underwriting/run", data={"demo_scenario": "image_upload"})
    assert res.status_code == 200
    view = res.json()
    assert view["decision"]["decision"] == "APPROVE"
    assert view["agents"]["compliance"]["critical_flags"] == []

    pan = next(d for d in view["document_files"] if d["type"] == "PAN_CARD")
    aadhaar = next(d for d in view["document_files"] if d["type"] == "AADHAAR_CARD")
    assert pan["filename"].endswith(".pdf")
    assert aadhaar["filename"].endswith(".pdf")

    for doc in (pan, aadhaar):
        dl = client.get(f"/api/v1/applications/{view['id']}/documents/{doc['id']}")
        assert dl.status_code == 200
        assert dl.headers["content-type"] == "application/pdf"
        assert dl.content.startswith(b"%PDF")

    pan_fields = client.get(f"/api/v1/applications/{view['id']}/documents/{pan['id']}/parsed").json()["extracted_fields"]
    assert pan_fields["pan_number"] == "ABCPS1234F"
    assert pan_fields["full_name"] == "Aarav Sharma"

    aadhaar_fields = client.get(f"/api/v1/applications/{view['id']}/documents/{aadhaar['id']}/parsed").json()["extracted_fields"]
    assert aadhaar_fields["aadhaar_number"] == "XXXX-XXXX-8921"
    assert "641035" in aadhaar_fields["address"]


def test_materialize_image_paths_converts_only_images():
    from app.services.applications import materialize_image_paths

    with tempfile.TemporaryDirectory() as tmp:
        png_path = os.path.join(tmp, "a.png")
        Image.new("RGB", (100, 100), "white").save(png_path)
        pdf_path = os.path.join(tmp, "b.pdf")
        open(pdf_path, "wb").close()

        paths, names = materialize_image_paths([png_path, pdf_path])
        assert paths[0].endswith(".pdf") and paths[0] != png_path
        assert names[0] == "a.pdf"
        assert paths[1] == pdf_path and names[1] == "b.pdf"


def test_upload_endpoint_rejects_unsupported_extension():
    client = TestClient(app)
    res = client.post(
        "/api/v1/underwriting/run",
        data={"name": "X", "monthly_income": "1", "loan_amount": "1"},
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert res.status_code == 400
    assert "PDF, JPG and PNG" in res.json()["detail"]
