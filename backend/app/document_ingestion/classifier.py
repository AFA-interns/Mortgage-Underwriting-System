"""
Document Classifier for Indian Mortgage Documents.
Classifies input documents into:
- PAN_CARD
- AADHAAR_CARD
- SALARY_SLIP
- FORM_16
- ITR
- BANK_STATEMENT
- PROPERTY_DEED
- UNKNOWN
Using multi-signal pattern scoring, keyword weight matrices, and structural regex anchors.
"""

import re
from typing import Dict, Tuple
from app.models.document_ingestion import DocumentType
from app.document_ingestion.preprocessor import PreprocessedDocument


class DocumentClassifier:
    """Classifies Indian financial & legal documents for mortgage underwriting."""

    # Weighted keyword signatures per document category
    SIGNATURES: Dict[DocumentType, Dict[str, float]] = {
        DocumentType.PAN_CARD: {
            "income tax department": 3.0,
            "permanent account number": 3.5,
            "govt. of india": 1.5,
            "father's name": 1.5,
            "date of birth": 1.0,
            "pan": 1.0,
            "signature": 0.5,
        },
        DocumentType.AADHAAR_CARD: {
            "unique identification authority of india": 4.0,
            "uidai": 3.0,
            "mera aadhaar": 3.0,
            "government of india": 1.5,
            "enrolment no": 2.0,
            "aadhaar": 2.5,
            "vid": 1.5,
            "male": 0.5,
            "female": 0.5,
            "help@uidai.gov.in": 2.0,
        },
        DocumentType.SALARY_SLIP: {
            "salary slip": 3.5,
            "payslip": 3.5,
            "pay slip": 3.5,
            "earnings": 2.0,
            "deductions": 2.0,
            "gross salary": 2.5,
            "net pay": 3.0,
            "basic pay": 2.0,
            "hra": 1.5,
            "provident fund": 1.5,
            "pf": 1.0,
            "employee id": 1.5,
            "employee code": 1.5,
            "designation": 1.0,
        },
        DocumentType.FORM_16: {
            "form no. 16": 4.0,
            "form 16": 3.5,
            "section 203": 3.0,
            "income-tax act, 1961": 2.5,
            "tan of deductor": 3.0,
            "tan of the deductor": 3.0,
            "pan of employee": 2.5,
            "pan of the employee": 2.5,
            "assessment year": 2.0,
            "quarter": 1.5,
            "total tax deducted": 2.0,
            "summary of tax deducted": 2.0,
        },
        DocumentType.ITR: {
            "indian income tax return": 4.0,
            "itr-v": 4.0,
            "itr-1": 3.5,
            "itr-2": 3.5,
            "acknowledgement number": 3.0,
            "gross total income": 2.5,
            "total taxable income": 2.5,
            "e-filing": 2.0,
            "income tax return verification form": 4.0,
        },
        DocumentType.BANK_STATEMENT: {
            "account statement": 3.5,
            "statement of account": 3.5,
            "bank statement": 3.5,
            "account number": 2.0,
            "ifsc": 2.5,
            "opening balance": 2.5,
            "closing balance": 2.5,
            "withdrawal": 1.5,
            "deposit": 1.5,
            "transaction date": 2.0,
            "narration": 1.5,
            "chq/ref no": 1.5,
            "dr / cr": 1.5,
        },
        DocumentType.PROPERTY_DEED: {
            "sale deed": 4.0,
            "deed of sale": 4.0,
            "allotment letter": 3.5,
            "possession letter": 3.0,
            "schedule property": 3.0,
            "sub-registrar": 3.0,
            "vendor": 2.0,
            "purchaser": 2.0,
            "consideration amount": 2.5,
            "super built-up area": 2.5,
            "carpet area": 2.5,
            "survey no": 2.0,
            "khata": 2.0,
            "flat no": 1.5,
        },
    }

    # Regex anchors
    REGEX_ANCHORS = {
        DocumentType.PAN_CARD: [
            re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]"),
            re.compile(r"Permanent\s+Account\s+Number", re.I),
        ],
        DocumentType.AADHAAR_CARD: [
            re.compile(r"\b\d{4}\s+\d{4}\s+\d{4}\b"),
            re.compile(r"\b[X\d]{4}[-\s][X\d]{4}[-\s]\d{4}\b"),
            re.compile(r"UIDAI|Unique\s+Identification", re.I),
        ],
        DocumentType.FORM_16: [
            re.compile(r"Form\s+(?:No\.?\s*)?16\b", re.I),
            re.compile(r"TAN\s*(?:of\s+the\s+deductor)?\s*[:\-]\s*[A-Z]{4}\d{5}[A-Z]", re.I),
        ],
        DocumentType.ITR: [
            re.compile(r"ITR-V|ITR-[1-7]", re.I),
            re.compile(r"Acknowledgment\s+Number", re.I),
        ],
        DocumentType.BANK_STATEMENT: [
            re.compile(r"IFSC\s*(?:Code)?\s*[:\-]?\s*[A-Z]{4}0[A-Z0-9]{6}", re.I),
            re.compile(r"Account\s+No|Statement\s+Period", re.I),
        ],
        DocumentType.SALARY_SLIP: [
            re.compile(r"Gross\s+Salary|Net\s+(?:Pay|Salary)", re.I),
            re.compile(r"Basic\s+(?:Pay|Salary)|HRA|Provident\s+Fund", re.I),
        ],
        DocumentType.PROPERTY_DEED: [
            re.compile(r"Sale\s+Deed|Agreement\s+for\s+Sale|Allotment\s+Letter", re.I),
            re.compile(r"Schedule\s+['\"]?A['\"]?|Schedule\s+Property", re.I),
        ],
    }

    @classmethod
    def classify(cls, doc: PreprocessedDocument) -> Tuple[DocumentType, float]:
        """
        Classify document and return (DocumentType, confidence_score).
        Confidence is normalized between 0.0 and 1.0.
        """
        text_lower = doc.raw_text.lower()
        filename_lower = doc.filename.lower()

        scores: Dict[DocumentType, float] = {dtype: 0.0 for dtype in cls.SIGNATURES.keys()}

        # 1. Filename heuristic boost
        if "pan" in filename_lower:
            scores[DocumentType.PAN_CARD] += 2.0
        if "aadhaar" in filename_lower or "aadhar" in filename_lower:
            scores[DocumentType.AADHAAR_CARD] += 2.0
        if "salary" in filename_lower or "payslip" in filename_lower or "pay_slip" in filename_lower:
            scores[DocumentType.SALARY_SLIP] += 2.5
        if "form16" in filename_lower or "form_16" in filename_lower:
            scores[DocumentType.FORM_16] += 2.5
        if "itr" in filename_lower or "tax_return" in filename_lower:
            scores[DocumentType.ITR] += 2.5
        if "bank" in filename_lower or "statement" in filename_lower:
            scores[DocumentType.BANK_STATEMENT] += 2.5
        if "property" in filename_lower or "deed" in filename_lower or "sale" in filename_lower:
            scores[DocumentType.PROPERTY_DEED] += 2.0

        # 2. Keyword density analysis
        for dtype, keywords in cls.SIGNATURES.items():
            for kw, weight in keywords.items():
                if kw in text_lower:
                    scores[dtype] += weight

        # 3. Regex pattern match boosts
        for dtype, regex_list in cls.REGEX_ANCHORS.items():
            for pattern in regex_list:
                if pattern.search(doc.raw_text):
                    scores[dtype] += 2.5

        # 4. Table structure heuristics
        if doc.metadata.get("has_tables", False):
            # Bank statement, Form 16, and salary slips typically have tables
            scores[DocumentType.BANK_STATEMENT] += 1.0
            scores[DocumentType.SALARY_SLIP] += 1.0
            scores[DocumentType.FORM_16] += 1.0

        # Determine highest scoring category
        best_doc_type = DocumentType.UNKNOWN
        max_score = 0.0

        for dtype, score in scores.items():
            if score > max_score:
                max_score = score
                best_doc_type = dtype

        if max_score < 2.0:
            return DocumentType.UNKNOWN, 0.30

        # Normalize score to confidence [0.5 - 0.99]
        normalized_confidence = min(0.99, max(0.60, 0.50 + (max_score / 25.0)))
        return best_doc_type, round(normalized_confidence, 3)
