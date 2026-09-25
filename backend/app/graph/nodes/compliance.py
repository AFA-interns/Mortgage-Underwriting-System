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


def _extract_compliance_input(state: dict[str, Any]) -> dict[str, Any]:
    """Reads UnderwritingState and shapes it into the plain-dict input the
    app.compliance check functions expect. See module docstring re: the
    upstream field-name assumption."""
    borrower_profile = state.get("borrower_profile", {}) or {}
    document_analysis = state.get("document_analysis", {}) or {}
    property_analysis = state.get("property_analysis", {}) or {}
    kyc = document_analysis.get("kyc", {}) or {}

    return {
        "kyc_documents": kyc.get("documents", []),
        "identity": document_analysis.get("borrower_identity", {}),
        "raw_fields": {**borrower_profile, **kyc},
        "pmla": kyc.get("pmla", {}),
        "loan_meta": {
            "loan_amount": borrower_profile.get("loan_amount"),
            "property_city_tier": borrower_profile.get("property_city_tier"),
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

    state["compliance_analysis"] = result.model_dump(mode="json")
    return state
