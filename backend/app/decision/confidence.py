"""Deterministic confidence engine — evidence reliability and consistency assessment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.decision import (
    AgentComparison,
    ConfidenceAssessment,
    Contradiction,
    Severity,
)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"confidence": {"base": 0.50, "completeness_weight": 0.25}}


def calculate_confidence(
    case: dict[str, Any],
    contradictions: list[Contradiction],
    comparison: AgentComparison,
    config_path: Path | str | None = None,
) -> ConfidenceAssessment:
    """Calculate deterministic confidence score based on evidence quality."""
    config = _load_config(config_path)
    conf_config = config.get("confidence", {})

    base = conf_config.get("base", 0.50)
    completeness_weight = conf_config.get("completeness_weight", 0.25)
    evidence_weight = conf_config.get("evidence_weight", 0.20)
    contradiction_penalty = conf_config.get("contradiction_penalty_per_high", 0.10)
    upstream_weight = conf_config.get("upstream_confidence_weight", 0.15)

    factors: dict[str, float] = {}
    score = base

    # 1. Completeness of inputs
    required = [
        "borrower_profile",
        "document_analysis",
        "credit_analysis",
        "property_analysis",
        "compliance_analysis",
    ]
    present = sum(1 for k in required if case.get(k))
    completeness = present / len(required)
    completeness_score = completeness * completeness_weight
    score += completeness_score
    factors["completeness"] = round(completeness, 3)

    # 2. Upstream agent confidence
    agent_confs = comparison.confidence_comparison
    agent_values = [v for v in agent_confs.values() if v]
    avg_upstream = sum(agent_values) / max(len(agent_values), 1)
    upstream_score = avg_upstream * upstream_weight
    score += upstream_score
    factors["upstream_confidence"] = round(avg_upstream, 3)

    # 3. Evidence availability (presence of provenance in document analysis)
    doc_analysis = case.get("document_analysis", {})
    provenance_count = len(doc_analysis.get("provenance", []))
    evidence_score = min(provenance_count / 10, 1.0) * evidence_weight
    score += evidence_score
    factors["evidence_availability"] = round(min(provenance_count / 10, 1.0), 3)

    # 4. Contradiction penalty
    high_contradictions = [
        c for c in contradictions if c.severity in (Severity.HIGH, Severity.CRITICAL)
    ]
    contradiction_penalty_total = len(high_contradictions) * contradiction_penalty
    score -= contradiction_penalty_total
    factors["contradiction_penalty"] = round(-contradiction_penalty_total, 3)

    # 5. Agent disagreement penalty
    if comparison.material_disagreement:
        score -= 0.10
        factors["agent_disagreement_penalty"] = -0.10

    # 6. Compliance ambiguity
    compliance = case.get("compliance_analysis", {})
    critical_flags = compliance.get("critical_flags", [])
    if critical_flags:
        penalty = min(len(critical_flags) * 0.05, 0.15)
        score -= penalty
        factors["compliance_penalty"] = round(-penalty, 3)

    score = max(0.0, min(1.0, score))

    # Determine threshold
    decision_config = config.get("decision", {})
    min_confidence = decision_config.get("minimum_confidence", 0.85)
    below_threshold = score < min_confidence

    reasoning_parts = []
    if completeness < 1.0:
        missing = [k for k in required if not case.get(k)]
        reasoning_parts.append(f"Inputs incomplete: missing {', '.join(missing)}")
    if high_contradictions:
        reasoning_parts.append(f"{len(high_contradictions)} high-severity contradictions")
    if comparison.material_disagreement:
        reasoning_parts.append("Material agent disagreement detected")
    if critical_flags:
        reasoning_parts.append(f"{len(critical_flags)} compliance critical flags")
    if below_threshold:
        reasoning_parts.append(f"Score {score:.3f} below threshold {min_confidence}")
    if not reasoning_parts:
        reasoning_parts.append("Evidence quality is acceptable")

    return ConfidenceAssessment(
        score=round(score, 4),
        factors=factors,
        below_threshold=below_threshold,
        reasoning="; ".join(reasoning_parts),
    )
