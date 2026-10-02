"""Credit bureau data access for the Credit Analysis Agent.

Bureau data can come from three places, tracked in the report's ``source``
field so downstream consumers (and the UI) can tell how much to trust it:

    SOURCE_BUREAU      a real bureau pull (CIBIL / Experian / Equifax / CRIF)
    SOURCE_DECLARED    a score entered by the applicant/loan officer
    SOURCE_SIMULATED   the deterministic stub - NOT derived from the borrower
    SOURCE_DEMO        fixed fixtures pinned for the bundled demo scenarios

A real bureau integration needs a lender agreement, credentials, applicant
consent and the PAN as lookup key. Until then ``fetch_from_bureau`` raises
``BureauNotConfigured`` and the pipeline falls back to the stub. When that
function is implemented, only it (and ``map_bureau_response``) should need to
change - the credit rules, scoring and UI read the same fields.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

SOURCE_BUREAU = "bureau"
SOURCE_DECLARED = "applicant_declared"
SOURCE_SIMULATED = "simulated"
SOURCE_DEMO = "demo_fixture"

SOURCE_LABELS = {
    SOURCE_BUREAU: "Credit bureau report",
    SOURCE_DECLARED: "Applicant-declared score",
    SOURCE_SIMULATED: "Simulated bureau data",
    SOURCE_DEMO: "Demo fixture",
}

# Sources whose values are not verified against a bureau.
UNVERIFIED_SOURCES = {SOURCE_DECLARED, SOURCE_SIMULATED, SOURCE_DEMO}

CIBIL_MIN, CIBIL_MAX = 300, 900


class BureauNotConfigured(RuntimeError):
    """No real bureau provider is configured."""


def validate_cibil_score(score: int) -> int:
    if not CIBIL_MIN <= score <= CIBIL_MAX:
        raise ValueError(f"CIBIL score must be between {CIBIL_MIN} and {CIBIL_MAX}.")
    return score


def is_verified(bureau_data: dict[str, Any]) -> bool:
    return bureau_data.get("source", SOURCE_SIMULATED) not in UNVERIFIED_SOURCES


def map_bureau_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Maps a provider response onto the fields the credit agent expects.

    ``cibil_score`` of None (or -1 / 0, which bureaus use for "NA") means the
    applicant is new-to-credit; the agent handles that as its own band.
    """
    score = raw.get("cibil_score")
    if score is not None and score <= 0:
        score = None
    return {
        "cibil_score": score,
        "settled_accounts": int(raw.get("settled_accounts", 0) or 0),
        "written_off_accounts": int(raw.get("written_off_accounts", 0) or 0),
        "max_dpd_last_12_months": int(raw.get("max_dpd_last_12_months", 0) or 0),
        "recent_enquiries_last_90_days": int(raw.get("recent_enquiries_last_90_days", 0) or 0),
        "credit_card_outstanding_total": float(raw.get("credit_card_outstanding_total", 0) or 0),
        "oldest_account_age_months": raw.get("oldest_account_age_months"),
        "source": SOURCE_BUREAU,
    }


def fetch_from_bureau(application_id: str) -> dict[str, Any]:
    """Real bureau pull. Not implemented: requires a bureau agreement.

    Implementation notes for whoever wires this up:
      * look the borrower up by PAN, fetched from the secure document store
        by ``application_id`` at call time - never put PAN on the graph state
        or in logs;
      * require a recorded applicant consent (see ``ApplicationStore``);
      * handle timeouts/outages by raising, so the caller can fall back or
        route the file to manual review rather than inventing data;
      * cache by PAN so the same person is not pulled twice;
      * return ``map_bureau_response(provider_payload)``.
    """
    provider = os.getenv("CREDIT_BUREAU_PROVIDER", "").strip().lower()
    raise BureauNotConfigured(
        f"No credit bureau provider is configured (CREDIT_BUREAU_PROVIDER={provider or 'unset'})."
    )


def fetch_credit_report(application_id: str) -> dict[str, Any]:
    """Deterministic SIMULATED report keyed by application_id.

    Nothing about the borrower goes into it, so it must never be treated as
    the applicant's real credit standing - the result is tagged
    ``source="simulated"`` for that reason. Settled/written-off accounts and
    DPD are always 0, so those red flags cannot trigger from this stub.
    """
    digest = hashlib.sha256(application_id.encode("utf-8")).hexdigest()
    pseudo_score = 300 + (int(digest[:4], 16) % 601)  # deterministic, 300-900

    return {
        "cibil_score": pseudo_score,
        "settled_accounts": 0,
        "written_off_accounts": 0,
        "max_dpd_last_12_months": 0,
        "recent_enquiries_last_90_days": int(digest[4], 16) % 3,
        "credit_card_outstanding_total": (int(digest[5:9], 16) % 200) * 1000.0,
        "oldest_account_age_months": 12 + (int(digest[9:11], 16) % 100),
        "source": SOURCE_SIMULATED,
    }


def declared_score_report(cibil_score: int) -> dict[str, Any]:
    """Bureau data built from a score the applicant/officer entered.

    Only the score is known; every other field is a neutral default, so the
    DPD / settled / written-off checks do not run on real information.
    """
    return {
        "cibil_score": validate_cibil_score(cibil_score),
        "settled_accounts": 0,
        "written_off_accounts": 0,
        "max_dpd_last_12_months": 0,
        "recent_enquiries_last_90_days": 0,
        "credit_card_outstanding_total": 0.0,
        "oldest_account_age_months": None,
        "source": SOURCE_DECLARED,
    }


def resolve_bureau_data(application_id: str, declared_cibil_score: int | None = None) -> dict[str, Any]:
    """Picks the best available bureau data, best source first:
    real bureau -> applicant-declared score -> simulated stub."""
    try:
        return fetch_from_bureau(application_id)
    except BureauNotConfigured:
        pass
    if declared_cibil_score is not None:
        return declared_score_report(declared_cibil_score)
    return fetch_credit_report(application_id)
