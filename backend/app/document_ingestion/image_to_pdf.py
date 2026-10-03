"""Converts a JPG/PNG upload into a single-page PDF so the rest of the
pipeline — classification, extraction, storage, the reviewer's document
viewer — only ever has to deal with PDFs.

The conversion alone does not make the page's text extractable (it is
still just a picture); app.document_ingestion.preprocessor OCRs any PDF
page that comes out with no text layer, which covers both this case and a
genuinely scanned PDF.
"""
from __future__ import annotations

import os

from PIL import Image, ImageOps

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def convert_image_to_pdf(src_path: str, dest_path: str | None = None) -> str:
    """Converts `src_path` (.jpg/.jpeg/.png) to a one-page PDF.

    Writes next to the source by default (same stem, .pdf extension).
    Returns the PDF's path. Raises ValueError for an unsupported extension
    or a file PIL can't open — the caller decides how to surface that.
    """
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ValueError(f"'{src_path}' is not a JPG or PNG file.")

    if dest_path is None:
        dest_path = os.path.splitext(src_path)[0] + ".pdf"

    with Image.open(src_path) as img:
        img = ImageOps.exif_transpose(img)  # phone photos often carry a rotation tag
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        img.save(dest_path, "PDF", resolution=200.0)

    return dest_path
