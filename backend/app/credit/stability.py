"""Income stability classification for CreditAnalysisResult.income_stability.

Values must match app.decision.risk_engine._score_stability's mapping:
"stable" | "moderately_stable" | "unstable" | "unknown".
"""
from __future__ import annotations

from app.credit.employment import EmploymentBucket
from app.credit.red_flags import count_severe_red_flags


def assess_income_stability(employment_type: EmploymentBucket, red_flags: list[str]) -> str:
    severe = count_severe_red_flags(red_flags)
    if employment_type == "salaried":
        return "unstable" if severe >= 1 else "stable"
    # self_employed / business - income is inherently less predictable, so
    # even a clean credit history only earns "moderately_stable", not "stable".
    return "unstable" if severe >= 1 else "moderately_stable"
