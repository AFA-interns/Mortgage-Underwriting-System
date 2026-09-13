"""Credit bureau integration - STUBBED.

# TODO: replace with a real CIBIL / Experian / Equifax / CRIF High Mark API
# call. For now this returns a deterministic mock report so the Credit
# Analysis Agent is fully runnable end-to-end without external credentials.
"""
from __future__ import annotations

import hashlib
from typing import Any


def fetch_credit_report(application_id: str) -> dict[str, Any]:
    """Deterministic mock bureau pull keyed by application_id.

    A real integration would key off PAN, not application_id - and PAN
    itself must never be stored or logged on this state object (see
    README_credit.md's KYC note). Callers that already have real or
    synthetic bureau data (tests, or a future real integration) should pass
    it via UnderwritingState["credit_bureau_data"] instead of relying on
    this stub - see app.graph.nodes.credit.credit_node.
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
    }
