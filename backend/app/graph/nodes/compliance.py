"""compliance_node — single LangGraph node entry point for the Compliance
Agent, mirroring app.graph.nodes.credit.credit_node's structure: one
function, reads shared state, calls into pure app.compliance modules,
writes state["compliance_analysis"] as a ComplianceAnalysisResult dict.

ASSUMPTION FLAGGED: the exact upstream field names read below
(document_analysis.kyc / document_analysis.borrower_identity /
property_analysis.rera_status / property_analysis.under_construction) are
inferred from README_decision.md's Document/Property Analysis input
contracts, since the Document Ingestion and Property Valuation agents'
real node code wasn't available when this was written. If those upstream
shapes differ once built, only `_extract_compliance_input` below needs to
change — every check function takes plain dicts and is upstream-agnostic.

Unlike credit_node, this node does NOT short-circuit on missing upstream
data: an empty/missing document_analysis naturally produces a
KYC_INCOMPLETE critical flag through the normal rules engine path, which
is the correct behavior per the design report ("incomplete KYC always
results in Suspend, never Approve") rather than a special-cased error.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.compliance.crew import run_compliance_reasoning
from app.compliance.config import get_compliance_config
from app.compliance.rules_engine import run_all_checks
from app.compliance.scoring import compute_confidence
from app.models.decision import ComplianceAnalysisResult, Evidence


_METRO_CITIES = {
    "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai",
    "kolkata", "hyderabad", "pune", "ahmedabad",
}


def _city_tier(city: str | None) -> str | None:
    return None if not city else ("metro" if city.strip().lower() in _METRO_CITIES else "non_metro")


def _from_doc_ingestion(doc_out: dict[str, Any], borrower_profile: dict[str, Any]) -> dict[str, Any]:
    """Maps the Document Ingestion Agent's real output (pan_card, aadhaar_card,
    salary_slips, ...) into the shapes the compliance checks expect."""
    pan = doc_out.get("pan_card") or {}
    aadhaar = doc_out.get("aadhaar_card") or {}
    kyc_profile = doc_out.get("borrower_kyc") or {}
    slips = doc_out.get("salary_slips") or []
    bank = doc_out.get("bank_statement") or {}
    prop = doc_out.get("property_profile") or {}

    address = aadhaar.get("address") or kyc_profile.get("residential_address")
    kyc_documents = [
        {"doc_type": "PAN", "present": bool(pan), "valid": bool(pan.get("is_valid_format", True))},
        {"doc_type": "AADHAAR", "present": bool(aadhaar), "valid": bool(aadhaar.get("is_valid_format", True))},
        # Aadhaar carries the residential address, so it doubles as address proof.
        {"doc_type": "ADDRESS_PROOF", "present": bool(address)},
    ]
    identity = {
        "application_form_name": borrower_profile.get("name") or kyc_profile.get("primary_name"),
        "pan_card_name": pan.get("full_name"),
        "aadhaar_name": aadhaar.get("full_name"),
        "salary_slip_name": slips[0].get("employee_name") if slips else None,
        "bank_account_name": bank.get("account_holder_name"),
        "application_form_dob": borrower_profile.get("dob"),
        "aadhaar_dob": aadhaar.get("dob"),
        "application_form_pan_number": borrower_profile.get("pan_number"),
        "pan_card_number": pan.get("pan_number"),
    }
    # Source of funds is evidenced by income documents; identity verification
    # is logged when both PAN and Aadhaar were extracted with a valid format.
    has_income_docs = bool(slips or bank or doc_out.get("form_16") or doc_out.get("itr_v"))
    pmla = {
        "source_of_funds_declared": has_income_docs,
        "identity_verification_logged": bool(pan.get("is_valid_format") and aadhaar.get("is_valid_format")),
    }
    return {
        "kyc_documents": kyc_documents,
        "identity": identity,
        "pmla": pmla,
        "city": prop.get("city"),
    }


def _extract_compliance_input(state: dict[str, Any]) -> dict[str, Any]:
    """Reads UnderwritingState and shapes it into the plain-dict input the
    app.compliance check functions expect. Prefers the Document Ingestion
    Agent's real output (doc_ingestion_output); falls back to the
    document_analysis.kyc contract when that is absent."""
    borrower_profile = state.get("borrower_profile", {}) or {}
    document_analysis = state.get("document_analysis", {}) or {}
    property_analysis = state.get("property_analysis", {}) or {}
    doc_out = state.get("doc_ingestion_output", {}) or {}
    kyc = document_analysis.get("kyc", {}) or {}

    if doc_out:
        mapped = _from_doc_ingestion(doc_out, borrower_profile)
    else:
        mapped = {
            "kyc_documents": kyc.get("documents", []),
            "identity": document_analysis.get("borrower_identity", {}),
            "pmla": kyc.get("pmla", {}),
            "city": None,
        }

    return {
        "kyc_documents": mapped["kyc_documents"],
        "identity": mapped["identity"],
        "raw_fields": {**borrower_profile, **kyc},
        "pmla": mapped["pmla"],
        "loan_meta": {
            "loan_amount": borrower_profile.get("loan_amount"),
            "property_city_tier": borrower_profile.get("property_city_tier")
            or _city_tier(mapped["city"]),
        },
        "property": {
            "under_construction": property_analysis.get("under_construction", False),
            "rera_status": property_analysis.get("rera_status", "unknown"),
        },
    }


def compliance_node(state: dict[str, Any]) -> dict[str, Any]:
    config = get_compliance_config()
    data = _extract_compliance_input(state)

    checks = run_all_checks(data, config)
    confidence = compute_confidence(checks["all_flags"], config)
    reasoning = run_compliance_reasoning(checks)

    now = datetime.now(UTC)
    evidence = [
        Evidence(
            agent="compliance",
            field=name,
            value=status,
            source="rules_engine",
            timestamp=now,
            confidence=confidence,
        )
        for name, status in checks["rule_status"].items()
    ]
    # LLM explanation isn't a field on ComplianceAnalysisResult (unlike
    # credit's `reasoning`) — carried as an evidence entry instead so it
    # survives into the report/audit trail without changing the shared model.
    evidence.append(
        Evidence(
            agent="compliance",
            field="reasoning",
            value=reasoning,
            source="compliance_crew",
            timestamp=now,
            confidence=confidence,
        )
    )

    result = ComplianceAnalysisResult(
        kyc_cdd=checks["kyc_cdd"],
        identity_consistency=checks["identity_consistency"],
        pmla_source_of_funds=checks["pmla_source_of_funds"],
        rbi_fair_practices=checks["rbi_fair_practices"],
        nhb=checks["nhb"],
        rera=checks["rera"],
        rule_status=checks["rule_status"],
        critical_flags=checks["critical_flags"],
        confidence=confidence,
        evidence=evidence,
    )

    # Return only this node's key: compliance runs in parallel with credit and
    # property, so returning the whole state causes concurrent-update errors.
    return {"compliance_analysis": result.model_dump(mode="json")}
