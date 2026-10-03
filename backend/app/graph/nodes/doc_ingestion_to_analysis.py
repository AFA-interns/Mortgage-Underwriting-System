from __future__ import annotations

from typing import Any

from app.graph.state import UnderwritingState


def _as_dict(value: Any) -> dict:
    """Safely convert value to dict, returning empty dict if not a dict."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    """Safely convert value to list, returning empty list if not a list."""
    return value if isinstance(value, list) else []


def doc_ingestion_to_analysis_node(state: UnderwritingState) -> dict[str, Any]:
    """Transform DocumentIngestionOutput to DocumentAnalysisResult format for downstream agents."""
    errors: list[dict[str, Any]] = list(state.get("errors", []))
    
    doc_out = _as_dict(state.get("doc_ingestion_output"))
    
    if not doc_out:
        errors.append({
            "stage": "doc_ingestion_transform",
            "message": "No doc_ingestion_output found in state",
        })
        return {"document_analysis": {}, "errors": errors}
    
    # Extract data from doc_ingestion_output with safe dict access
    docs_meta = _as_list(doc_out.get("documents_metadata"))
    pan = _as_dict(doc_out.get("pan_card"))
    aadhaar = _as_dict(doc_out.get("aadhaar_card"))
    salary_slips = _as_list(doc_out.get("salary_slips"))
    form_16 = _as_dict(doc_out.get("form_16"))
    itr = _as_dict(doc_out.get("itr_v"))
    bank_stmt = _as_dict(doc_out.get("bank_statement"))
    prop_doc = _as_dict(doc_out.get("property_document"))
    borrower_kyc = _as_dict(doc_out.get("borrower_kyc"))
    borrower_income = _as_dict(doc_out.get("borrower_income"))
    borrower_liab = _as_dict(doc_out.get("borrower_liabilities"))
    checklist = _as_dict(doc_out.get("checklist"))
    reconciliation = _as_dict(doc_out.get("reconciliation"))
    confidence = _as_dict(doc_out.get("confidence"))
    human_review = _as_dict(doc_out.get("human_review"))
    
    # Build documents list
    documents = []
    for m in docs_meta:
        m_dict = _as_dict(m)
        documents.append({
            "type": m_dict.get("document_type", "UNKNOWN"),
            "status": "processed" if m_dict.get("page_count", 0) > 0 else "empty",
        })
    
    # Missing documents from checklist
    missing_docs = _as_list(checklist.get("missing_documents"))
    
    # Contradictions from reconciliation
    contradictions = []
    for c in _as_list(reconciliation.get("contradictions")):
        c_dict = _as_dict(c)
        contradictions.append({
            "field": c_dict.get("field", ""),
            "severity": c_dict.get("severity", "MEDIUM"),
            "description": c_dict.get("description", ""),
        })
    
    # Build verification status
    total_docs = len(documents)
    verified_docs = sum(1 for d in documents if d.get("status") == "processed")
    if total_docs == 0:
        verification_status = "unknown"
    elif verified_docs == total_docs:
        verification_status = "verified"
    else:
        verification_status = "partial"
    
    # Provenance/evidence
    provenance = []
    if pan:
        provenance.append({"agent": "document", "field": "pan", "value": pan.get("pan_number")})
    if aadhaar:
        provenance.append({"agent": "document", "field": "aadhaar", "value": aadhaar.get("aadhaar_number")})
    for s in salary_slips:
        s_dict = _as_dict(s)
        if s_dict.get("gross_salary"):
            provenance.append({"agent": "document", "field": "salary", "value": s_dict.get("gross_salary")})
    
    # Extraction confidence
    extraction_conf = 0.0
    extraction_conf = confidence.get("overall_confidence", 0.0)
    
    document_analysis = {
        "verification_status": verification_status,
        "documents": documents,
        "borrower_identity": {
            "name": borrower_kyc.get("primary_name") or pan.get("full_name") or aadhaar.get("full_name"),
            "verified": bool(pan or aadhaar),
        },
        "income": {
            "monthly_income": borrower_income.get("monthly_gross_salary", 0),
            "annual_gross": borrower_income.get("annual_gross_income_form16", 0),
            "employer": borrower_income.get("employer_name"),
            "salary_slips_count": borrower_income.get("salary_slips_provided_count", 0),
        },
        "assets": {
            "total": borrower_liab.get("detected_monthly_emis", 0) * 12 * 5,
        },
        "liabilities": {
            "total": borrower_liab.get("detected_monthly_emis", 0) * 12 * 5,
        },
        "kyc": {
            "status": "complete" if (pan and aadhaar) else "incomplete",
            "pan_valid": bool(pan),
            "aadhaar_valid": bool(aadhaar),
        },
        "missing_documents": missing_docs,
        "contradictions": contradictions,
        "extraction_confidence": extraction_conf,
        "provenance": provenance,
        "flags": [],
    }
    
    # Add flags based on conditions
    if missing_docs:
        document_analysis["flags"].append("missing_documents")
    if contradictions:
        document_analysis["flags"].append("contradictions_detected")
    if not (pan and aadhaar):
        document_analysis["flags"].append("incomplete_kyc")
    
    return {
        "document_analysis": document_analysis,
        "doc_ingestion_output": state.get("doc_ingestion_output", {}),
        "errors": errors,
    }