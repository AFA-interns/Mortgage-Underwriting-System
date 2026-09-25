"""Synthetic test data for the Decision Agent."""
from __future__ import annotations

import os
from typing import Any

import pytest

# Tests use the in-memory store; never touch a developer's PostgreSQL.
os.environ["DATABASE_URL"] = ""

from tests.mock_data.generate_docs import generate_all_mock_scenarios


def get_good_case() -> dict[str, Any]:
    """A strong application — should APPROVE."""
    return {
        "application_id": "APP-001",
        "borrower_profile": {
            "name": "Priya Sharma",
            "age": 32,
            "monthly_income": 150000,
            "employment_type": "salaried",
            "employer": "Tata Consultancy Services",
            "loan_amount": 5000000,
            "loan_tenure_months": 240,
            "property_value": 8000000,
            "existing_debt": 0,
        },
        "document_analysis": {
            "verification_status": "verified",
            "documents": [{"type": "aadhaar"}, {"type": "salary_slip"}, {"type": "bank_statement"}],
            "borrower_identity": {"name": "Priya Sharma", "verified": True},
            "income": {"monthly_income": 150000},
            "assets": {"total": 2000000},
            "liabilities": {"total": 0},
            "kyc": {"status": "complete"},
            "missing_documents": [],
            "contradictions": [],
            "extraction_confidence": 0.95,
            "provenance": [{"agent": "document", "field": "income", "value": 150000}],
            "flags": [],
        },
        "credit_analysis": {
            "cibil_score": 780,
            "credit_risk_tier": "low",
            "foir": 0.25,
            "monthly_obligations": 15000,
            "ltv": 0.625,
            "income_stability": "stable",
            "confidence": 0.92,
            "flags": [],
            "evidence": [{"agent": "credit", "field": "cibil", "value": 780}],
            "raw_data": {"monthly_income": 150000, "property_value": 8000000},
        },
        "property_analysis": {
            "estimated_value": 8200000,
            "market_range_low": 7500000,
            "market_range_high": 8900000,
            "valuation_confidence": 0.88,
            "price_per_sqft": 8500,
            "comparables": [{"price": 8000000}, {"price": 8300000}],
            "registry_circle_rate_comparison": {"difference_percent": 3.5},
            "valuation_variance_percent": 2.5,
            "rera_status": "registered",
            "flags": [],
            "evidence": [{"agent": "property", "field": "valuation", "value": 8200000}],
        },
        "compliance_analysis": {
            "kyc_cdd": {"status": "complete", "level": "enhanced"},
            "identity_consistency": "consistent",
            "pmla_source_of_funds": {"status": "clear", "source": "salary"},
            "rbi_fair_practices": {"status": "compliant"},
            "nhb": {"status": "not_applicable"},
            "rera": {"status": "registered"},
            "rule_status": {"kyc": "PASS", "pmla": "PASS", "rbi": "PASS"},
            "critical_flags": [],
            "confidence": 0.94,
            "evidence": [{"agent": "compliance", "field": "kyc", "value": "complete"}],
        },
    }


def get_weak_case() -> dict[str, Any]:
    """A weak application — should DENY."""
    return {
        "application_id": "APP-002",
        "borrower_profile": {
            "name": "Rahul Kumar",
            "age": 28,
            "monthly_income": 25000,
            "employment_type": "self-employed",
            "employer": "N/A",
            "loan_amount": 6000000,
            "loan_tenure_months": 240,
            "property_value": 7000000,
            "existing_debt": 15000,
        },
        "document_analysis": {
            "verification_status": "partial",
            "documents": [{"type": "aadhaar"}],
            "borrower_identity": {"name": "Rahul Kumar", "verified": True},
            "income": {"monthly_income": 25000},
            "assets": {"total": 500000},
            "liabilities": {"total": 150000},
            "kyc": {"status": "partial"},
            "missing_documents": ["salary_slip", "bank_statement", "itr"],
            "contradictions": [],
            "extraction_confidence": 0.60,
            "provenance": [],
            "flags": ["income_not_verified"],
        },
        "credit_analysis": {
            "cibil_score": 520,
            "credit_risk_tier": "high",
            "foir": 0.72,
            "monthly_obligations": 15000,
            "ltv": 0.857,
            "income_stability": "unstable",
            "confidence": 0.55,
            "flags": ["low_cibil", "high_foir"],
            "evidence": [],
            "raw_data": {"monthly_income": 25000, "property_value": 7000000},
        },
        "property_analysis": {
            "estimated_value": 5500000,
            "market_range_low": 5000000,
            "market_range_high": 6000000,
            "valuation_confidence": 0.45,
            "price_per_sqft": 5500,
            "comparables": [],
            "registry_circle_rate_comparison": {"difference_percent": 27},
            "valuation_variance_percent": 27.3,
            "rera_status": "not_registered",
            "flags": ["high_variance", "not_rera"],
            "evidence": [],
        },
        "compliance_analysis": {
            "kyc_cdd": {"status": "incomplete"},
            "identity_consistency": "consistent",
            "pmla_source_of_funds": {"status": "unclear"},
            "rbi_fair_practices": {"status": "compliant"},
            "nhb": {"status": "not_applicable"},
            "rera": {"status": "not_registered"},
            "rule_status": {"kyc": "INCOMPLETE", "pmla": "UNCLEAR"},
            "critical_flags": [],
            "confidence": 0.50,
            "evidence": [],
        },
    }


def get_suspend_case() -> dict[str, Any]:
    """An ambiguous application — should SUSPEND."""
    return {
        "application_id": "APP-003",
        "borrower_profile": {
            "name": "Ananya Patel",
            "age": 35,
            "monthly_income": 80000,
            "employment_type": "salaried",
            "employer": "Infosys",
            "loan_amount": 5000000,
            "loan_tenure_months": 240,
            "property_value": 7500000,
            "existing_debt": 20000,
        },
        "document_analysis": {
            "verification_status": "partial",
            "documents": [{"type": "aadhaar"}, {"type": "salary_slip"}],
            "borrower_identity": {"name": "Ananya Patel", "verified": True},
            "income": {"monthly_income": 80000},
            "assets": {"total": 1500000},
            "liabilities": {"total": 200000},
            "kyc": {"status": "complete"},
            "missing_documents": ["bank_statement"],
            "contradictions": [
                {
                    "field": "monthly_income",
                    "severity": "HIGH",
                    "sources": [
                        {"agent": "document", "value": 80000},
                        {"agent": "credit", "value": 60000},
                    ],
                    "resolution": "UNRESOLVED",
                    "description": "Income mismatch: 25% difference",
                }
            ],
            "extraction_confidence": 0.75,
            "provenance": [{"agent": "document", "field": "income", "value": 80000}],
            "flags": [],
        },
        "credit_analysis": {
            "cibil_score": 680,
            "credit_risk_tier": "moderate",
            "foir": 0.42,
            "monthly_obligations": 20000,
            "ltv": 0.667,
            "income_stability": "moderately_stable",
            "confidence": 0.70,
            "flags": ["moderate_risk"],
            "evidence": [{"agent": "credit", "field": "cibil", "value": 680}],
            "raw_data": {"monthly_income": 60000, "property_value": 7500000},
        },
        "property_analysis": {
            "estimated_value": 7200000,
            "market_range_low": 6500000,
            "market_range_high": 7900000,
            "valuation_confidence": 0.70,
            "price_per_sqft": 7200,
            "comparables": [{"price": 7100000}],
            "registry_circle_rate_comparison": {"difference_percent": 4.0},
            "valuation_variance_percent": 4.0,
            "rera_status": "registered",
            "flags": [],
            "evidence": [{"agent": "property", "field": "valuation", "value": 7200000}],
        },
        "compliance_analysis": {
            "kyc_cdd": {"status": "complete"},
            "identity_consistency": "consistent",
            "pmla_source_of_funds": {"status": "pending"},
            "rbi_fair_practices": {"status": "compliant"},
            "nhb": {"status": "not_applicable"},
            "rera": {"status": "registered"},
            "rule_status": {"kyc": "PASS", "pmla": "PENDING"},
            "critical_flags": [],
            "confidence": 0.65,
            "evidence": [],
        },
    }


def get_missing_inputs_case() -> dict[str, Any]:
    """A case with missing required inputs — should SUSPEND."""
    return {
        "application_id": "APP-004",
        "borrower_profile": {
            "name": "Test User",
        },
        "credit_analysis": None,
        "property_analysis": {},
        "compliance_analysis": {},
    }


@pytest.fixture(scope="session")
def mock_docs():
    """Generates and returns paths to all mock test document suites."""
    return generate_all_mock_scenarios()
