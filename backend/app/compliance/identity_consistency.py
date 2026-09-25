"""Cross-document identity consistency check.

Populates ComplianceAnalysisResult.identity_consistency (a plain status
string, unlike the other checks which are dicts). Uses rapidfuzz so
formatting differences (abbreviations, middle names) don't produce false
mismatches — matches app.credit's use of the same library for a similar
purpose.
"""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from app.models.decision import Severity

from .flags import RuleFlag


def _names_match(a: str | None, b: str | None, threshold: int) -> bool:
    if not a or not b:
        return True  # missing data isn't a mismatch — handled by KYC check
    return fuzz.token_sort_ratio(a.lower(), b.lower()) >= threshold


def check_identity_consistency(
    data: dict[str, Any], config: dict
) -> tuple[str, list[RuleFlag]]:
    threshold = config.get("fuzzy_match", {}).get("name_match_threshold", 90)
    identity = data.get("identity", {})
    flags: list[RuleFlag] = []

    reference_name = identity.get("application_form_name")
    other_names = {
        "pan_card": identity.get("pan_card_name"),
        "aadhaar": identity.get("aadhaar_name"),
        "salary_slip": identity.get("salary_slip_name"),
        "bank_account": identity.get("bank_account_name"),
    }

    for source, name in other_names.items():
        if name is None or reference_name is None:
            continue
        if not _names_match(reference_name, name, threshold):
            flags.append(
                RuleFlag(
                    code="IDENTITY_MISMATCH_NAME",
                    severity=Severity.MEDIUM,
                    message=(
                        f"Name on {source.replace('_', ' ')} ('{name}') does not "
                        f"match application form ('{reference_name}')."
                    ),
                )
            )

    dob_form = identity.get("application_form_dob")
    dob_aadhaar = identity.get("aadhaar_dob")
    if dob_form and dob_aadhaar and dob_form != dob_aadhaar:
        flags.append(
            RuleFlag(
                code="IDENTITY_MISMATCH_DOB",
                severity=Severity.HIGH,
                message=(
                    f"DOB on Aadhaar ('{dob_aadhaar}') does not match "
                    f"application form ('{dob_form}')."
                ),
            )
        )

    pan_form = identity.get("application_form_pan_number")
    pan_card = identity.get("pan_card_number")
    if pan_form and pan_card and pan_form != pan_card:
        flags.append(
            RuleFlag(
                code="IDENTITY_MISMATCH_PAN",
                severity=Severity.CRITICAL,
                message="PAN number on application form does not match PAN card.",
            )
        )

    if any(f.severity == Severity.CRITICAL for f in flags):
        status = "FAIL"
    elif flags:
        status = "WARNING"
    else:
        status = "PASS"

    return status, flags
