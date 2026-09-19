"""
Document Pre-processing and Text Layer Extraction Module.
Handles PDF reading (PyMuPDF / pdfplumber), text extraction, table extraction,
image metadata inspection, and page text layout analysis.
"""

import os
import io
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
from typing import List, Dict, Any, Optional, Tuple


class PreprocessedDocument:
    def __init__(
        self,
        file_path: str,
        filename: str,
        file_type: str,
        page_count: int,
        raw_text: str,
        pages_text: List[str],
        tables: List[List[List[str]]],
        metadata: Dict[str, Any],
    ):
        self.file_path = file_path
        self.filename = filename
        self.file_type = file_type
        self.page_count = page_count
        self.raw_text = raw_text
        self.pages_text = pages_text
        self.tables = tables
        self.metadata = metadata


class DocumentPreprocessor:
    """Preprocesses PDF, PNG, and JPEG files for extraction and classification."""

    SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff"}

    @classmethod
    def process_file(cls, file_path: str) -> PreprocessedDocument:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format '{ext}'. Supported: {cls.SUPPORTED_EXTENSIONS}")

        file_size = os.path.getsize(file_path)

        if ext == ".pdf":
            return cls._process_pdf(file_path, filename, file_size)
        else:
            return cls._process_image(file_path, filename, ext, file_size)

    @classmethod
    def _process_pdf(cls, file_path: str, filename: str, file_size: int) -> PreprocessedDocument:
        pages_text = []
        full_text_list = []
        tables_list = []

        # 1. PyMuPDF extraction for fast full text and metadata
        doc = fitz.open(file_path)
        page_count = len(doc)
        pdf_metadata = doc.metadata or {}

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_text = page.get_text("text") or ""
            pages_text.append(page_text)
            full_text_list.append(page_text)

        doc.close()

        # 2. pdfplumber extraction for structured tables (critical for salary slips, bank statements, Form 16)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted_tables = page.extract_tables()
                    if extracted_tables:
                        for tbl in extracted_tables:
                            # Clean None values in table cells
                            cleaned_tbl = [
                                [str(cell).strip() if cell is not None else "" for cell in row]
                                for row in tbl
                                if any(cell is not None and str(cell).strip() for cell in row)
                            ]
                            if cleaned_tbl:
                                tables_list.append(cleaned_tbl)
        except Exception:
            # Fallback gracefully if pdfplumber encounters non-standard font structures
            pass

        raw_text = "\n--- PAGE BREAK ---\n".join(full_text_list)

        metadata = {
            "file_size_bytes": file_size,
            "page_count": page_count,
            "creator": pdf_metadata.get("creator", ""),
            "producer": pdf_metadata.get("producer", ""),
            "has_tables": len(tables_list) > 0,
            "table_count": len(tables_list),
            "text_length": len(raw_text),
        }

        return PreprocessedDocument(
            file_path=file_path,
            filename=filename,
            file_type="PDF",
            page_count=page_count,
            raw_text=raw_text,
            pages_text=pages_text,
            tables=tables_list,
            metadata=metadata,
        )

    @classmethod
    def _process_image(cls, file_path: str, filename: str, ext: str, file_size: int) -> PreprocessedDocument:
        img = Image.open(file_path)
        width, height = img.size

        # In a full OCR setup or standard PDF/image pipeline, we inspect image properties
        metadata = {
            "file_size_bytes": file_size,
            "page_count": 1,
            "image_width": width,
            "image_height": height,
            "image_mode": img.mode,
            "has_tables": False,
            "table_count": 0,
        }

        return PreprocessedDocument(
            file_path=file_path,
            filename=filename,
            file_type=ext.upper().replace(".", ""),
            page_count=1,
            raw_text="",  # Raw text filled by OCR module if image
            pages_text=[""],
            tables=[],
            metadata=metadata,
        )
