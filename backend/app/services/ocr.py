"""OCR for scanned/photographed documents (Tesseract via pytesseract).

Used by app.document_ingestion.preprocessor when a PDF page has no
extractable text layer — true for every image-to-PDF conversion (feature:
JPG/PNG upload) and for genuinely scanned PDFs. Never raises: when
Tesseract isn't installed or OCR fails, callers get "" back and fall through
to the existing low-confidence / human-review path, same as an unreadable
document does today.

Configuration (backend/.env):
    TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
        Only needed when `tesseract` isn't on PATH. A few common Windows
        install locations are checked automatically before giving up.
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

_COMMON_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)

_checked = False
_available = False


def _locate_tesseract() -> str | None:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured:
        return configured
    if shutil.which("tesseract"):
        return "tesseract"
    for path in _COMMON_WINDOWS_PATHS:
        if os.path.isfile(path):
            return path
    return None


def ocr_available() -> bool:
    """True once a working Tesseract install has been located (cached)."""
    global _checked, _available
    if _checked:
        return _available
    _checked = True
    try:
        import pytesseract

        cmd = _locate_tesseract()
        if not cmd:
            logger.info("Tesseract OCR not found; image/scanned-document text extraction is disabled.")
            _available = False
            return False
        pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()
        _available = True
    except Exception as exc:
        logger.info("Tesseract OCR unavailable (%s); image/scanned-document text extraction is disabled.", exc)
        _available = False
    return _available


def ocr_image(image: "Image.Image") -> str:
    """OCRs a single page image. Returns "" on any failure (never raises)."""
    if not ocr_available():
        return ""
    try:
        import pytesseract

        return pytesseract.image_to_string(image) or ""
    except Exception as exc:
        logger.warning("OCR failed on a page: %s", exc)
        return ""
