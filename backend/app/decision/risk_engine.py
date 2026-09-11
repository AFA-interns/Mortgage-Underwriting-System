"""Deterministic risk engine — weighted scoring with configurable weights and bands."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.decision import RiskAssessment, RiskComponent, RiskLevel

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "risk": {
            "weights": {
                "credit": 0.25,
                "foir": 0.20,
                "ltv": 0.15,
                "property": 0.15,
                "documents": 0.15,
                "stability": 0.10,
            },
            "bands": {"low": 80, "moderate": 60, "high": 40},
        }
    }


def _score_credit_history(credit: dict[str, Any]) -> tuple[float, list[str]]:
    """Score credit history 0-100 (higher = better)."""
    factors: list[str] = []
    score = 50.0

    cibil = credit.get("cibil_score")
    if cibil is not None:
        if cibil >= 750:
            score += 30
            factors.append(f"Excellent CIBIL score ({cibil})")
        elif cibil >= 700:
            score += 20
            factors.append(f"Good CIBIL score ({cibil})")
        elif cibil >= 650:
            score += 5
            factors.append(f"Fair CIBIL score ({cibil})")
        elif cibil >= 550:
            score -= 10
            factors.append(f"Below-average CIBIL score ({cibil})")
        else:
            score -= 30
            factors.append(f"Poor CIBIL score ({cibil})")
    else:
        score -= 20
        factors.append("No CIBIL score available")

    tier = credit.get("credit_risk_tier", "unknown")
    if tier == "low":
        score += 10
        factors.append("Low credit risk tier")
    elif tier == "high":
        score -= 15
        factors.append("High credit risk tier")

    return max(0, min(100, score)), factors


def _score_foir(credit: dict[str, Any]) -> tuple[float, list[str]]:
    """Score FOIR (lower FOIR = higher score)."""
    factors: list[str] = []
    foir = credit.get("foir")
    if foir is None:
        return 50.0, ["FOIR not available"]

    if foir <= 0.30:
        score = 95
        factors.append(f"Excellent FOIR ({foir:.0%})")
    elif foir <= 0.40:
        score = 80
        factors.append(f"Good FOIR ({foir:.0%})")
    elif foir <= 0.50:
        score = 60
        factors.append(f"Moderate FOIR ({foir:.0%})")
    elif foir <= 0.60:
        score = 35
        factors.append(f"High FOIR ({foir:.0%})")
    else:
        score = 15
        factors.append(f"Very high FOIR ({foir:.0%})")

    return score, factors


def _score_ltv(credit: dict[str, Any], borrower: dict[str, Any]) -> tuple[float, list[str]]:
    """Score LTV (lower LTV = higher score)."""
    factors: list[str] = []
    ltv = credit.get("ltv")

    if ltv is None:
        loan = borrower.get("loan_amount", 0)
        prop = borrower.get("property_value", 0)
        if prop > 0:
            ltv = loan / prop

    if ltv is None:
        return 50.0, ["LTV not calculable"]

    if ltv <= 0.60:
        score = 95
        factors.append(f"Excellent LTV ({ltv:.0%})")
    elif ltv <= 0.70:
        score = 80
        factors.append(f"Good LTV ({ltv:.0%})")
    elif ltv <= 0.80:
        score = 60
        factors.append(f"Moderate LTV ({ltv:.0%})")
    elif ltv <= 0.90:
        score = 35
        factors.append(f"High LTV ({ltv:.0%})")
    else:
        score = 15
        factors.append(f"Very high LTV ({ltv:.0%})")

    return score, factors


def _score_property(property_data: dict[str, Any]) -> tuple[float, list[str]]:
    """Score property valuation confidence."""
    factors: list[str] = []
    conf = property_data.get("valuation_confidence", 0)
    rera = property_data.get("rera_status", "unknown")

    if conf >= 0.8:
        score = 90
        factors.append(f"High valuation confidence ({conf:.0%})")
    elif conf >= 0.6:
        score = 70
        factors.append(f"Moderate valuation confidence ({conf:.0%})")
    elif conf >= 0.4:
        score = 45
        factors.append(f"Low valuation confidence ({conf:.0%})")
    else:
        score = 20
        factors.append(f"Very low valuation confidence ({conf:.0%})")

    if rera == "registered":
        score = min(100, score + 10)
        factors.append("RERA registered property")
    elif rera == "not_registered":
        score = max(0, score - 10)
        factors.append("Property not RERA registered")

    variance = property_data.get("valuation_variance_percent", 0)
    if abs(variance) > 20:
        score = max(0, score - 15)
        factors.append(f"High valuation variance ({variance:.1f}%)")

    return max(0, min(100, score)), factors


def _score_documents(doc_analysis: dict[str, Any]) -> tuple[float, list[str]]:
    """Score document completeness and quality."""
    factors: list[str] = []
    missing = doc_analysis.get("missing_documents", [])
    extraction_conf = doc_analysis.get("extraction_confidence", 0)
    verification = doc_analysis.get("verification_status", "unknown")

    if not missing:
        score = 85
        factors.append("All required documents present")
    elif len(missing) <= 2:
        score = 60
        factors.append(f"{len(missing)} document(s) missing")
    else:
        score = 30
        factors.append(f"{len(missing)} documents missing")

    if extraction_conf >= 0.8:
        score = min(100, score + 10)
        factors.append("High extraction confidence")
    elif extraction_conf < 0.5:
        score = max(0, score - 10)
        factors.append("Low extraction confidence")

    if verification == "verified":
        score = min(100, score + 5)
        factors.append("Documents verified")

    return max(0, min(100, score)), factors


def _score_stability(credit: dict[str, Any]) -> tuple[float, list[str]]:
    """Score financial/income stability."""
    factors: list[str] = []
    stability = credit.get("income_stability", "unknown")

    mapping = {
        "stable": (90, "Stable income history"),
        "moderately_stable": (70, "Moderately stable income"),
        "unstable": (35, "Unstable income"),
        "unknown": (50, "Income stability unknown"),
    }
    score, factor = mapping.get(stability, (50, "Income stability unknown"))
    factors.append(factor)

    return score, factors


def calculate_risk_score(
    document: dict[str, Any],
    credit: dict[str, Any],
    property_data: dict[str, Any],
    compliance: dict[str, Any],
    borrower: dict[str, Any] | None = None,
    config_path: Path | str | None = None,
) -> RiskAssessment:
    """Calculate deterministic weighted risk score."""
    if borrower is None:
        borrower = {}

    try:
        config = _load_config(config_path)
        weights = config["risk"]["weights"]
        bands = config["risk"]["bands"]

        components: list[RiskComponent] = []

        # Credit History
        credit_score, credit_factors = _score_credit_history(credit)
        components.append(RiskComponent(
            name="credit_history",
            weight=weights["credit"],
            raw_score=credit_score,
            weighted_score=credit_score * weights["credit"],
            factors=credit_factors,
        ))

        # FOIR
        foir_score, foir_factors = _score_foir(credit)
        components.append(RiskComponent(
            name="foir",
            weight=weights["foir"],
            raw_score=foir_score,
            weighted_score=foir_score * weights["foir"],
            factors=foir_factors,
        ))

        # LTV
        ltv_score, ltv_factors = _score_ltv(credit, borrower)
        components.append(RiskComponent(
            name="ltv",
            weight=weights["ltv"],
            raw_score=ltv_score,
            weighted_score=ltv_score * weights["ltv"],
            factors=ltv_factors,
        ))

        # Property
        prop_score, prop_factors = _score_property(property_data)
        components.append(RiskComponent(
            name="property",
            weight=weights["property"],
            raw_score=prop_score,
            weighted_score=prop_score * weights["property"],
            factors=prop_factors,
        ))

        # Documents
        doc_score, doc_factors = _score_documents(document)
        components.append(RiskComponent(
            name="documents",
            weight=weights["documents"],
            raw_score=doc_score,
            weighted_score=doc_score * weights["documents"],
            factors=doc_factors,
        ))

        # Financial Stability
        stab_score, stab_factors = _score_stability(credit)
        components.append(RiskComponent(
            name="stability",
            weight=weights["stability"],
            raw_score=stab_score,
            weighted_score=stab_score * weights["stability"],
            factors=stab_factors,
        ))

        total_score = sum(c.weighted_score for c in components)
        total_score = max(0, min(100, total_score))

        # Risk level
        if total_score >= bands["low"]:
            level = RiskLevel.LOW
        elif total_score >= bands["moderate"]:
            level = RiskLevel.MODERATE
        elif total_score >= bands["high"]:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH

        all_positive = []
        all_risk = []
        positive_keywords = [
            "excellent",
            "good",
            "stable",
            "high conf",
            "present",
            "verified",
            "registered",
        ]
        risk_keywords = [
            "poor",
            "high foir",
            "high ltv",
            "missing",
            "low",
            "unstable",
            "variance",
            "not registered",
            "no cibil",
        ]
        for c in components:
            for f in c.factors:
                if any(w in f.lower() for w in positive_keywords):
                    all_positive.append(f)
                elif any(w in f.lower() for w in risk_keywords):
                    all_risk.append(f)

        return RiskAssessment(
            score=round(total_score, 1),
            level=level,
            components=components,
            key_positive_factors=all_positive,
            key_risk_factors=all_risk,
            calculation_failed=False,
        )

    except Exception as e:
        return RiskAssessment(
            score=0,
            level=RiskLevel.VERY_HIGH,
            calculation_failed=True,
            key_risk_factors=[f"Risk calculation failed: {e}"],
        )
