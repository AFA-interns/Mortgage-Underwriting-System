"""Employment-type normalization shared across the Credit Analysis Agent.

BorrowerProfile.employment_type is a free-text string from the Document
Ingestion Agent (observed values include "salaried" and "self-employed" with
a hyphen) - normalize it to the three buckets our FOIR/red-flag rules use.
"""
from __future__ import annotations

EmploymentBucket = str  # "salaried" | "self_employed" | "business"


def normalize_employment_type(raw: str) -> EmploymentBucket:
    normalized = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in ("salaried", "salary", "employee", "employed"):
        return "salaried"
    if normalized in ("business", "businessman", "businesswoman", "proprietor", "partnership"):
        return "business"
    # self_employed, self-employed, freelance, professional, or unrecognized -
    # default to the stricter self-employed FOIR threshold rather than
    # assuming salaried when employment type is ambiguous or missing.
    return "self_employed"
