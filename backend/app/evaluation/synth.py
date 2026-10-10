"""Generate synthetic labeled ground-truth data for Decision Agent evaluation.

Labels are assigned by underwriting design intent (strong/weak/ambiguous files),
independent of what the model predicts — so metrics reflect real agreement.

Run from backend/:  python -m app.evaluation.synth
Writes data/labeled_cases.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evaluation.runner import run_deterministic_pipeline
from app.evaluation.schemas import LabeledCase

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labeled_cases.json"

_QUALITY: dict[str, dict[str, Any]] = {
    "strong": {
        "verification_status": "verified",
        "missing_documents": [],
        "extraction_confidence": 0.95,
        "provenance_n": 8,
        "doc_flags": [],
        "credit_confidence": 0.92,
        "valuation_confidence": 0.90,
        "rera_status": "registered",
        "valuation_variance_percent": 2.5,
        "compliance_confidence": 0.94,
        "kyc_status": "complete",
        "pmla_status": "clear",
        "rbi_status": "compliant",
        "critical_flags": [],
    },
    "weak": {
        "verification_status": "partial",
        "missing_documents": ["salary_slip", "bank_statement", "itr"],
        "extraction_confidence": 0.70,
        "provenance_n": 8,
        "doc_flags": ["income_not_verified"],
        "credit_confidence": 0.75,
        "valuation_confidence": 0.55,
        "rera_status": "not_registered",
        "valuation_variance_percent": 26.0,
        "compliance_confidence": 0.70,
        "kyc_status": "incomplete",
        "pmla_status": "unclear",
        "rbi_status": "compliant",
        "critical_flags": [],
    },
    "moderate": {
        "verification_status": "partial",
        "missing_documents": ["bank_statement"],
        "extraction_confidence": 0.85,
        "provenance_n": 6,
        "doc_flags": [],
        "credit_confidence": 0.80,
        "valuation_confidence": 0.68,
        "rera_status": "registered",
        "valuation_variance_percent": 4.5,
        "compliance_confidence": 0.72,
        "kyc_status": "complete",
        "pmla_status": "pending",
        "rbi_status": "compliant",
        "critical_flags": [],
    },
}

_DOC_TYPES = ["aadhaar", "salary_slip", "bank_statement", "itr", "property_deed", "kyc_form"]
_PROVENANCE_FIELDS = [
    "income",
    "employer",
    "salary_slip",
    "bank_statement",
    "itr",
    "property_deed",
    "kyc",
    "asset_statement",
]

_TIER_FLAGS = {
    "low": [],
    "moderate": ["moderate_risk"],
    "high": ["low_cibil", "high_foir"],
}


def _provenance(n: int) -> list[dict[str, Any]]:
    return [
        {"agent": "document", "field": field, "value": "verified"}
        for field in _PROVENANCE_FIELDS[:n]
    ]


def build_case(
    app_id: str,
    name: str,
    age: int,
    income: float,
    loan: float,
    prop_value: float,
    debt: float,
    quality: str,
    cibil: int,
    tier: str,
    foir: float,
    stability: str,
    employment: str = "salaried",
    employer: str = "Tata Consultancy Services",
    critical_flags: list[str] | None = None,
    credit_income_ratio: float | None = None,
    property_agent_value: float | None = None,
) -> dict[str, Any]:
    """Build one pipeline-input dict with consistent cross-agent values."""
    q = _QUALITY[quality]
    ltv = round(loan / prop_value, 3)
    doc_income = income
    credit_income = income if credit_income_ratio is None else income * credit_income_ratio
    estimated_value = property_agent_value if property_agent_value is not None else prop_value
    flags = list(q["critical_flags"] if critical_flags is None else critical_flags)
    obligations = debt if debt > 0 else round(income * 0.1, 2)
    documents = [{"type": t} for t in _DOC_TYPES if t not in q["missing_documents"]]

    return {
        "application_id": app_id,
        "borrower_profile": {
            "name": name,
            "age": age,
            "monthly_income": income,
            "employment_type": employment,
            "employer": employer,
            "loan_amount": loan,
            "loan_tenure_months": 240,
            "property_value": prop_value,
            "existing_debt": debt,
            "cibil_score": cibil,
        },
        "document_analysis": {
            "verification_status": q["verification_status"],
            "documents": documents,
            "borrower_identity": {"name": name, "verified": True},
            "income": {"monthly_income": doc_income},
            "assets": {"total": max(income * 12, 500000)},
            "liabilities": {"total": debt},
            "kyc": {"status": q["kyc_status"]},
            "missing_documents": list(q["missing_documents"]),
            "contradictions": [],
            "extraction_confidence": q["extraction_confidence"],
            "provenance": _provenance(q["provenance_n"]),
            "flags": list(q["doc_flags"]),
        },
        "credit_analysis": {
            "cibil_score": cibil,
            "credit_risk_tier": tier,
            "foir": foir,
            "monthly_obligations": obligations,
            "ltv": ltv,
            "income_stability": stability,
            "confidence": q["credit_confidence"],
            "flags": list(_TIER_FLAGS.get(tier, [])),
            "evidence": [{"agent": "credit", "field": "cibil", "value": cibil}],
            "raw_data": {
                "monthly_income": credit_income,
                "property_value": prop_value,
            },
        },
        "property_analysis": {
            "estimated_value": estimated_value,
            "market_range_low": round(prop_value * 0.95, 2),
            "market_range_high": round(prop_value * 1.05, 2),
            "valuation_confidence": q["valuation_confidence"],
            "price_per_sqft": round(prop_value / 1200, 2),
            "comparables": [{"price": round(prop_value * 0.98, 2)}],
            "registry_circle_rate_comparison": {"difference_percent": 3.5},
            "valuation_variance_percent": q["valuation_variance_percent"],
            "rera_status": q["rera_status"],
            "flags": [],
            "evidence": [
                {"agent": "property", "field": "valuation", "value": estimated_value}
            ],
        },
        "compliance_analysis": {
            "kyc_cdd": {"status": q["kyc_status"], "level": "standard"},
            "identity_consistency": "consistent",
            "pmla_source_of_funds": {"status": q["pmla_status"], "source": "salary"},
            "rbi_fair_practices": {"status": q["rbi_status"]},
            "nhb": {"status": "not_applicable"},
            "rera": {"status": q["rera_status"]},
            "rule_status": {"kyc": q["kyc_status"].upper(), "pmla": q["pmla_status"].upper()},
            "critical_flags": flags,
            "confidence": q["compliance_confidence"],
            "evidence": [{"agent": "compliance", "field": "kyc", "value": q["kyc_status"]}],
        },
    }


# (label, outcome, kwargs for build_case)
_CASE_SPECS: list[dict[str, Any]] = [
    # ── Clear approvals — strong files (label APPROVE) ──
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-001", "name": "Priya Sharma",
     "age": 32, "income": 175000, "loan": 5000000, "prop_value": 8500000, "debt": 15000,
     "quality": "strong", "cibil": 810, "tier": "low", "foir": 0.28, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-002", "name": "Amit Verma",
     "age": 41, "income": 220000, "loan": 7500000, "prop_value": 12000000, "debt": 30000,
     "quality": "strong", "cibil": 780, "tier": "low", "foir": 0.30, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-003", "name": "Sneha Iyer",
     "age": 29, "income": 140000, "loan": 3500000, "prop_value": 6000000, "debt": 0,
     "quality": "strong", "cibil": 830, "tier": "low", "foir": 0.25, "stability": "stable"},
    {"label": "APPROVE", "outcome": "default", "app_id": "LBL-004", "name": "Vikram Singh",
     "age": 38, "income": 300000, "loan": 9000000, "prop_value": 15000000, "debt": 90000,
     "quality": "strong", "cibil": 760, "tier": "low", "foir": 0.32, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-005", "name": "Kavita Rao",
     "age": 35, "income": 120000, "loan": 4000000, "prop_value": 7000000, "debt": 10000,
     "quality": "strong", "cibil": 795, "tier": "low", "foir": 0.27, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-006", "name": "Rohan Mehta",
     "age": 45, "income": 190000, "loan": 6000000, "prop_value": 9500000, "debt": 25000,
     "quality": "strong", "cibil": 750, "tier": "low", "foir": 0.31, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-007", "name": "Meera Joshi",
     "age": 33, "income": 250000, "loan": 8000000, "prop_value": 14000000, "debt": 40000,
     "quality": "strong", "cibil": 820, "tier": "low", "foir": 0.26, "stability": "stable"},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-008", "name": "Arjun Nair",
     "age": 31, "income": 160000, "loan": 4500000, "prop_value": 7200000, "debt": 12000,
     "quality": "strong", "cibil": 765, "tier": "low", "foir": 0.29, "stability": "stable"},
    {"label": "APPROVE", "outcome": "default", "app_id": "LBL-009", "name": "Deepa Kulkarni",
     "age": 37, "income": 210000, "loan": 6500000, "prop_value": 11000000, "debt": 35000,
     "quality": "strong", "cibil": 805, "tier": "low", "foir": 0.30, "stability": "stable"},

    # ── Borderline-strong — approvable file, conservative policy suspends (label APPROVE) ──
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-010", "name": "Sanjay Gupta",
     "age": 44, "income": 130000, "loan": 4200000, "prop_value": 5800000, "debt": 20000,
     "quality": "moderate", "cibil": 735, "tier": "low", "foir": 0.35, "stability": "stable",
     "missing_override": ["bank_statement", "itr"]},
    {"label": "APPROVE", "outcome": "paid", "app_id": "LBL-011", "name": "Neha Bansal",
     "age": 27, "income": 110000, "loan": 3200000, "prop_value": 4600000, "debt": 8000,
     "quality": "moderate", "cibil": 745, "tier": "low", "foir": 0.33, "stability": "stable",
     "extraction_override": 0.78},

    # ── Clear denials — impaired credit / unsustainable debt (label DENY) ──
    {"label": "DENY", "outcome": None, "app_id": "LBL-012", "name": "Rahul Chauhan",
     "age": 28, "income": 30000, "loan": 5500000, "prop_value": 6200000, "debt": 18000,
     "quality": "weak", "cibil": 520, "tier": "high", "foir": 0.74, "stability": "unstable",
     "employment": "self-employed", "employer": "N/A"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-013", "name": "Farhan Qureshi",
     "age": 34, "income": 45000, "loan": 6800000, "prop_value": 7400000, "debt": 25000,
     "quality": "weak", "cibil": 545, "tier": "high", "foir": 0.68, "stability": "unstable",
     "employment": "self-employed", "employer": "N/A"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-014", "name": "Sunita Devi",
     "age": 52, "income": 38000, "loan": 4800000, "prop_value": 5200000, "debt": 22000,
     "quality": "weak", "cibil": 505, "tier": "high", "foir": 0.71, "stability": "unstable"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-015", "name": "Manish Agarwal",
     "age": 40, "income": 55000, "loan": 7000000, "prop_value": 7500000, "debt": 30000,
     "quality": "weak", "cibil": 560, "tier": "high", "foir": 0.66, "stability": "unstable",
     "employment": "self-employed", "employer": "N/A"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-016", "name": "Pooja Rathore",
     "age": 30, "income": 35000, "loan": 4200000, "prop_value": 4800000, "debt": 16000,
     "quality": "weak", "cibil": 535, "tier": "high", "foir": 0.70, "stability": "unstable"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-017", "name": "Imran Sheikh",
     "age": 47, "income": 42000, "loan": 5100000, "prop_value": 5600000, "debt": 24000,
     "quality": "weak", "cibil": 550, "tier": "high", "foir": 0.69, "stability": "unstable",
     "employment": "self-employed", "employer": "N/A"},

    # ── Borderline-weak — impaired file, conservative policy suspends for review (label DENY) ──
    {"label": "DENY", "outcome": None, "app_id": "LBL-018", "name": "Rakesh Yadav",
     "age": 36, "income": 60000, "loan": 5800000, "prop_value": 7100000, "debt": 28000,
     "quality": "moderate", "cibil": 590, "tier": "high", "foir": 0.58, "stability": "unstable"},
    {"label": "DENY", "outcome": None, "app_id": "LBL-019", "name": "Anita Deshmukh",
     "age": 43, "income": 65000, "loan": 6200000, "prop_value": 7800000, "debt": 32000,
     "quality": "moderate", "cibil": 575, "tier": "high", "foir": 0.62, "stability": "unstable"},

    # ── Ambiguous mid-band files → human review (label SUSPEND) ──
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-020", "name": "Ananya Patel",
     "age": 35, "income": 80000, "loan": 5000000, "prop_value": 7500000, "debt": 20000,
     "quality": "moderate", "cibil": 680, "tier": "moderate", "foir": 0.45,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-021", "name": "Joseph Thomas",
     "age": 39, "income": 95000, "loan": 5600000, "prop_value": 8200000, "debt": 35000,
     "quality": "moderate", "cibil": 665, "tier": "moderate", "foir": 0.48,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-022", "name": "Lakshmi Menon",
     "age": 31, "income": 72000, "loan": 4400000, "prop_value": 6400000, "debt": 18000,
     "quality": "moderate", "cibil": 690, "tier": "moderate", "foir": 0.43,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-023", "name": "Tanvi Shah",
     "age": 28, "income": 68000, "loan": 3800000, "prop_value": 5500000, "debt": 12000,
     "quality": "moderate", "cibil": 672, "tier": "moderate", "foir": 0.46,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-024", "name": "Harish Kumar",
     "age": 49, "income": 110000, "loan": 6400000, "prop_value": 8800000, "debt": 45000,
     "quality": "moderate", "cibil": 655, "tier": "moderate", "foir": 0.49,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-025", "name": "Rekha Jain",
     "age": 42, "income": 88000, "loan": 5200000, "prop_value": 7600000, "debt": 26000,
     "quality": "moderate", "cibil": 685, "tier": "moderate", "foir": 0.44,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-026", "name": "Deepak Chopra",
     "age": 37, "income": 76000, "loan": 4700000, "prop_value": 6800000, "debt": 21000,
     "quality": "moderate", "cibil": 668, "tier": "moderate", "foir": 0.47,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-027", "name": "Shalini Bose",
     "age": 33, "income": 84000, "loan": 4900000, "prop_value": 7300000, "debt": 23000,
     "quality": "moderate", "cibil": 678, "tier": "moderate", "foir": 0.42,
      "stability": "moderately_stable"},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-028", "name": "Gaurav Tripathi",
     "age": 46, "income": 102000, "loan": 6100000, "prop_value": 8600000, "debt": 38000,
     "quality": "moderate", "cibil": 661, "tier": "moderate", "foir": 0.50,
      "stability": "moderately_stable"},

    # ── Regulatory blocks → must be reviewed regardless of credit quality (label SUSPEND) ──
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-029", "name": "Karan Malhotra",
     "age": 36, "income": 260000, "loan": 8500000, "prop_value": 13500000, "debt": 50000,
     "quality": "strong", "cibil": 790, "tier": "low", "foir": 0.29, "stability": "stable",
     "critical_flags": ["FRAUD_ALERT"]},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-030", "name": "Vandana Pillai",
     "age": 44, "income": 240000, "loan": 7800000, "prop_value": 12500000, "debt": 45000,
     "quality": "strong", "cibil": 775, "tier": "low", "foir": 0.30, "stability": "stable",
     "critical_flags": ["SANCTIONS_SCREENING_HIT"]},

    # ── Untrustworthy data → cannot decide (label SUSPEND) ──
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-031", "name": "Devendra Rao",
     "age": 34, "income": 90000, "loan": 5300000, "prop_value": 7700000, "debt": 27000,
     "quality": "moderate", "cibil": 675, "tier": "moderate", "foir": 0.45,
     "stability": "moderately_stable", "credit_income_ratio": 0.6},
    {"label": "SUSPEND", "outcome": None, "app_id": "LBL-032", "name": "Partial File User",
     "age": 30, "income": 0, "loan": 0, "prop_value": 0, "debt": 0,
     "quality": "moderate", "cibil": 0, "tier": "moderate", "foir": 0.0,
     "stability": "unknown", "missing_inputs": True},
]


def _apply_overrides(case: dict[str, Any], spec: dict[str, Any]) -> None:
    if spec.get("missing_override") is not None:
        case["document_analysis"]["missing_documents"] = list(spec["missing_override"])
        case["document_analysis"]["documents"] = [
            {"type": t}
            for t in _DOC_TYPES
            if t not in spec["missing_override"]
        ]
    if spec.get("extraction_override") is not None:
        case["document_analysis"]["extraction_confidence"] = spec["extraction_override"]


def build_dataset() -> list[LabeledCase]:
    """Build all labeled cases with ground-truth labels."""
    cases: list[LabeledCase] = []
    for spec in _CASE_SPECS:
        if spec.get("missing_inputs"):
            case = {
                "application_id": spec["app_id"],
                "borrower_profile": {"name": spec["name"], "age": spec["age"]},
                "document_analysis": {},
                "credit_analysis": {},
                "property_analysis": {},
                "compliance_analysis": {},
            }
        else:
            case = build_case(
                app_id=spec["app_id"],
                name=spec["name"],
                age=spec["age"],
                income=spec["income"],
                loan=spec["loan"],
                prop_value=spec["prop_value"],
                debt=spec["debt"],
                quality=spec["quality"],
                cibil=spec["cibil"],
                tier=spec["tier"],
                foir=spec["foir"],
                stability=spec["stability"],
                employment=spec.get("employment", "salaried"),
                employer=spec.get("employer", "Tata Consultancy Services"),
                critical_flags=spec.get("critical_flags"),
                credit_income_ratio=spec.get("credit_income_ratio"),
            )
            _apply_overrides(case, spec)

        cases.append(
            LabeledCase.model_validate(
                {
                    **case,
                    "ground_truth_decision": spec["label"],
                    "outcome": spec.get("outcome"),
                }
            )
        )
    return cases


def main() -> int:
    cases = build_dataset()

    print(f"{'app_id':<10} {'label':<9} {'predicted':<9} {'risk':>6} {'conf':>6} {'gate':<30}")
    print("-" * 78)
    for case in cases:
        prediction = run_deterministic_pipeline(case.as_pipeline_input())
        case.predicted = prediction
        print(
            f"{case.application_id:<10} "
            f"{case.ground_truth_decision.value:<9} "
            f"{prediction.decision.value:<9} "
            f"{prediction.risk_score:>6.1f} "
            f"{prediction.confidence:>6.3f} "
            f"{prediction.gate_triggered or '-':<30}"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cases": [c.model_dump(mode="json", exclude={"predicted"}) for c in cases]}
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {len(cases)} labeled cases to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
