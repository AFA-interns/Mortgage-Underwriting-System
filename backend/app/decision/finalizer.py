"""Deterministic finalizer — authoritative safety gates and APPROVE/DENY/SUSPEND logic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.decision.contradiction_detector import has_unresolved_critical
from app.models.decision import (
    ConfidenceAssessment,
    Contradiction,
    DecisionCrewOutput,
    DecisionResult,
    DecisionType,
    RiskAssessment,
)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"decision": {"approve_min_score": 80, "deny_max_score": 40, "minimum_confidence": 0.85}}


def _critical_compliance_flag(compliance: dict[str, Any]) -> bool:
    critical_flags = compliance.get("critical_flags", [])
    return len(critical_flags) > 0


def _material_crew_disagreement(crew: DecisionCrewOutput | None) -> bool:
    if crew is None or crew.error:
        return False
    recs = []
    for member in [crew.underwriter, crew.risk_analyst]:
        if member and member.recommendation:
            recs.append(member.recommendation)
    if len(recs) < 2:
        return False
    return recs[0] != recs[1]


def _crew_suspends(crew: DecisionCrewOutput | None) -> bool:
    if crew is None:
        return False
    for member in [crew.underwriter, crew.risk_analyst]:
        if member and member.recommendation == DecisionType.SUSPEND:
            return True
    return False


def _gather_all_evidence(
    case: dict[str, Any],
    risk: RiskAssessment,
    crew: DecisionCrewOutput | None,
) -> list[dict[str, Any]]:
    evidence = []
    agent_keys = [
        "document_analysis",
        "credit_analysis",
        "property_analysis",
        "compliance_analysis",
    ]
    for agent_key in agent_keys:
        agent_data = case.get(agent_key) or {}
        for ev in agent_data.get("evidence", agent_data.get("provenance", [])):
            evidence.append(ev if isinstance(ev, dict) else ev.model_dump())
    for comp in risk.components:
        for f in comp.factors:
            evidence.append({"source": "risk_engine", "field": comp.name, "value": f})
    if crew:
        for member in [crew.underwriter, crew.risk_analyst, crew.report_writer]:
            if member:
                for f in member.key_factors:
                    evidence.append(
                    {
                        "source": member.role.value,
                        "field": "key_factor",
                        "value": f,
                    }
                )
    return evidence


def deterministic_finalize(
    case: dict[str, Any],
    risk: RiskAssessment,
    confidence: ConfidenceAssessment,
    contradictions: list[Contradiction],
    compliance: dict[str, Any],
    crew_result: DecisionCrewOutput | None = None,
    config_path: Path | str | None = None,
) -> DecisionResult:
    """Authoritative deterministic finalization — cannot be overridden by LLM."""
    application_id = case.get("application_id", "UNKNOWN")
    config = _load_config(config_path)
    decision_config = config.get("decision", {})
    approve_min = decision_config.get("approve_min_score", 80)
    deny_max = decision_config.get("deny_max_score", 40)
    min_confidence = decision_config.get("minimum_confidence", 0.85)

    errors: list[str] = []
    rationale_parts: list[str] = []
    human_review_required = True

    # ── Hard Safety Gates ──
    if _critical_compliance_flag(compliance):
        rationale_parts.append("Critical compliance flag present → SUSPEND")
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=risk.key_risk_factors + ["Critical compliance flag"],
            compliance_status="BLOCKED",
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if not case.get("borrower_profile") or not case.get("credit_analysis"):
        rationale_parts.append("Required input data missing → SUSPEND")
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=risk.key_risk_factors + ["Missing required data"],
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if has_unresolved_critical(contradictions):
        rationale_parts.append("Unresolved critical contradiction → SUSPEND")
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=risk.key_risk_factors + ["Unresolved critical contradiction"],
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if confidence.score < min_confidence:
        rationale_parts.append(
            f"Confidence {confidence.score:.3f} < threshold {min_confidence} → SUSPEND"
        )
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=risk.key_risk_factors + ["Low confidence"],
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if _material_crew_disagreement(crew_result):
        rationale_parts.append("Material crew disagreement → SUSPEND")
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=risk.key_risk_factors + ["Material crew disagreement"],
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if risk.calculation_failed:
        rationale_parts.append("Required risk calculation failed → SUSPEND")
        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.SUSPEND,
            risk_score=0,
            risk_level=risk.level,
            confidence=confidence.score,
            key_risk_factors=["Risk calculation failure"],
            human_review_required=True,
            rationale="; ".join(rationale_parts),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if crew_result and crew_result.error:
        errors.append(crew_result.error)
        rationale_parts.append(
            f"Crew execution error: {crew_result.error} → "
            "proceeding with deterministic assessment only"
        )

    # ── Score-Based Finalization ──
    if risk.score >= approve_min:
        human_review_required = False
        rationale_parts.append(
            f"Risk score {risk.score:.1f} >= approval threshold {approve_min} → APPROVE"
        )
        compliance_status = "PASS"
        critical_flags = compliance.get("critical_flags", [])
        if critical_flags:
            compliance_status = "CONDITIONAL"
            human_review_required = True
            rationale_parts.append(f"Compliance conditional: {len(critical_flags)} flags")

        return DecisionResult(
            application_id=application_id,
            decision=DecisionType.APPROVE,
            risk_score=risk.score,
            risk_level=risk.level,
            confidence=confidence.score,
            key_positive_factors=risk.key_positive_factors,
            key_risk_factors=risk.key_risk_factors,
            compliance_status=compliance_status,
            human_review_required=human_review_required,
            rationale="; ".join(rationale_parts),
            agent_consensus=_build_consensus(crew_result),
            evidence=_gather_all_evidence(case, risk, crew_result),
            errors=errors,
        )

    if risk.score <= deny_max:
        if confidence.score >= min_confidence:
            rationale_parts.append(
                f"Risk score {risk.score:.1f} <= denial threshold {deny_max} → DENY"
            )
            return DecisionResult(
                application_id=application_id,
                decision=DecisionType.DENY,
                risk_score=risk.score,
                risk_level=risk.level,
                confidence=confidence.score,
                key_risk_factors=risk.key_risk_factors,
                compliance_status="PASS" if not compliance.get("critical_flags") else "FLAGGED",
                human_review_required=True,  # Denials always need human review
                rationale="; ".join(rationale_parts),
                agent_consensus=_build_consensus(crew_result),
                evidence=_gather_all_evidence(case, risk, crew_result),
                errors=errors,
            )
        else:
            rationale_parts.append(
                f"Risk score {risk.score:.1f} in denial range but confidence "
                f"{confidence.score:.3f} insufficient → SUSPEND"
            )
            return DecisionResult(
                application_id=application_id,
                decision=DecisionType.SUSPEND,
                risk_score=risk.score,
                risk_level=risk.level,
                confidence=confidence.score,
                key_risk_factors=risk.key_risk_factors + ["Insufficient confidence for denial"],
                human_review_required=True,
                rationale="; ".join(rationale_parts),
                evidence=_gather_all_evidence(case, risk, crew_result),
                errors=errors,
            )

    # ── Review Zone ──
    rationale_parts.append(
        f"Risk score {risk.score:.1f} in review zone ({deny_max}-{approve_min}) → SUSPEND"
    )
    return DecisionResult(
        application_id=application_id,
        decision=DecisionType.SUSPEND,
        risk_score=risk.score,
        risk_level=risk.level,
        confidence=confidence.score,
        key_positive_factors=risk.key_positive_factors,
        key_risk_factors=risk.key_risk_factors,
        human_review_required=True,
        rationale="; ".join(rationale_parts),
        agent_consensus=_build_consensus(crew_result),
        evidence=_gather_all_evidence(case, risk, crew_result),
        errors=errors,
    )


def _build_consensus(crew: DecisionCrewOutput | None) -> dict[str, Any]:
    if crew is None:
        return {}
    consensus: dict[str, Any] = {}
    members = [
        ("underwriter", crew.underwriter),
        ("risk_analyst", crew.risk_analyst),
        ("report_writer", crew.report_writer),
    ]
    for name, member in members:
        if member:
            consensus[name] = {
                "recommendation": member.recommendation.value if member.recommendation else None,
                "confidence": member.confidence,
                "reasoning": member.reasoning,
            }
    return consensus
