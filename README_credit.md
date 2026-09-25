# Credit Analysis Agent

The Credit Analysis Agent sits between Document Ingestion and Property Valuation in the Mortgage Underwriting pipeline. It turns a borrower's declared financials into a structured, evidence-backed credit risk assessment for Indian housing finance: CIBIL band, FOIR, LTV, income stability, red flags, a composite risk score, and its own **preliminary** APPROVE/CONDITIONAL/REJECT recommendation.

**Core principle: deterministic rules decide; the LLM only explains.** This is the same principle the Decision Agent's crew follows (see `README_decision.md`) - every field on `credit_analysis` except `reasoning` is plain, auditable Python.

**This is not the final loan decision.** `credit_analysis.preliminary_decision` is this agent's own credit-specific call - the Decision Agent still runs its own independent 6-component risk engine and rule-based crew over `credit_analysis`'s other fields before reaching `decision.decision`.

---

## Table of Contents

1. [Pipeline](#pipeline)
2. [Module Layout](#module-layout)
3. [Input Contract](#input-contract)
4. [Output Contract](#output-contract)
5. [CIBIL Bands](#cibil-bands)
6. [FOIR](#foir)
7. [LTV](#ltv)
8. [Red Flags](#red-flags)
9. [Income Stability](#income-stability)
10. [Composite Risk Score](#composite-risk-score)
11. [Confidence](#confidence)
12. [Preliminary Decision Rules](#preliminary-decision-rules)
13. [LLM Reasoning](#llm-reasoning)
14. [Configuration](#configuration)
15. [KYC / PAN Note](#kyc--pan-note)
16. [What's Stubbed](#whats-stubbed)
17. [Tests](#tests)

---

## Pipeline

`credit_node` (`backend/app/graph/nodes/credit.py`) runs as a single LangGraph node, mirroring how `decision_node` orchestrates the Decision Agent as one function calling into several pure modules:

```
1. Read borrower_profile (monthly_income, loan_amount, loan_tenure_months,
   property_value, existing_debt, employment_type)
2. Fetch credit bureau data (state["credit_bureau_data"] override, or the
   stubbed app.services.credit_bureau)
3. calculate_emi(...)              -> proposed EMI for the loan being applied for
4. get_credit_band / get_credit_risk_tier
5. calculate_foir / calculate_monthly_obligations
6. calculate_ltv
7. detect_red_flags
8. assess_income_stability
9. compute_confidence / compute_credit_risk_score
10. generate_preliminary_decision   -> APPROVE | CONDITIONAL | REJECT
11. run_credit_reasoning(...)       -> LLM explains steps 1-10, never changes them
```

If `monthly_income`, `loan_amount`, or `loan_tenure_months` is missing or non-positive, the node short-circuits after step 1: it records a `{"stage": "credit_analysis", ...}` error and returns a mostly-empty `CreditAnalysisResult` (no bureau fetch, no LLM call).

Integration into `backend/app/graph/workflow.py`'s `StateGraph` is left for whoever wires the full ingestion → credit → property → compliance → decision chain together - this branch only adds the node function, matching how the `ashfaque-decision-agent` branch added `decision_node` without chaining it to non-existent upstream agents either.

---

## Module Layout

```
backend/
├── config/
│   └── credit_config.yaml              # CIBIL bands, FOIR thresholds, weights, decision cutoffs
├── app/
│   ├── agents/
│   │   └── credit/
│   │       └── crew.py                 # Deterministic explanation text (no LLM)
│   ├── credit/
│   │   ├── config.py                   # YAML loader + in-code fallback defaults
│   │   ├── employment.py               # employment_type string normalization
│   │   ├── cibil.py                    # CIBIL band + risk-tier mapping
│   │   ├── foir.py                     # EMI calc, FOIR, monthly_obligations
│   │   ├── ltv.py                      # Loan-to-Value
│   │   ├── red_flags.py                # Deterministic red-flag checklist
│   │   ├── stability.py                # income_stability classification
│   │   └── scoring.py                  # confidence, risk_score, preliminary_decision
│   ├── graph/
│   │   └── nodes/
│   │       └── credit.py               # credit_node entry point
│   ├── models/
│   │   └── decision.py                 # CreditAnalysisResult, CreditDecisionType (extended, shared file)
│   └── services/
│       └── credit_bureau.py            # Stubbed bureau fetch - TODO real API
└── tests/
    ├── test_credit_cibil.py
    ├── test_credit_foir.py
    ├── test_credit_ltv.py
    ├── test_credit_red_flags.py
    ├── test_credit_stability.py
    ├── test_credit_scoring.py
    ├── test_credit_crew.py             # Summary builder only, no real LLM call
    └── test_credit_node.py             # Full node, LLM reasoning monkeypatched
```

---

## Input Contract

Reads `state["borrower_profile"]` (`BorrowerProfile` in `app/models/decision.py`, populated by the Document Ingestion Agent):

```json
{
  "application_id": "APP-001",
  "name": "Priya Sharma",
  "employment_type": "salaried",
  "monthly_income": 150000,
  "loan_amount": 5000000,
  "loan_tenure_months": 240,
  "property_value": 8000000,
  "existing_debt": 0
}
```

`employment_type` is free text from upstream OCR/forms (`"salaried"`, `"self-employed"`, etc.) - `app.credit.employment.normalize_employment_type` maps it to `salaried` / `self_employed` / `business`, defaulting unrecognized values to the stricter `self_employed` FOIR threshold rather than assuming `salaried`.

`existing_debt` is treated as the borrower's declared existing monthly EMI burden (the FOIR formula's "existing EMIs" term). `property_value` is the borrower's *declared* value, used for a preliminary LTV check - the authoritative valuation is `property_analysis.estimated_value` from the Property Valuation Agent, and the Decision Agent's contradiction detector cross-checks the two.

Optionally reads `state["credit_bureau_data"]` (see [What's Stubbed](#whats-stubbed)).

---

## Output Contract

Writes `state["credit_analysis"]` as a `CreditAnalysisResult` dict:

```json
{
  "cibil_score": 780,
  "credit_risk_tier": "low",
  "credit_band": "Excellent",
  "foir": 0.2744,
  "monthly_obligations": 24700.0,
  "ltv": 0.625,
  "income_stability": "stable",
  "confidence": 0.9,
  "risk_score": 95.23,
  "preliminary_decision": "APPROVE",
  "reasoning": "The applicant has an excellent CIBIL score, comfortable FOIR headroom, and no adverse credit history - the loan is approved without conditions.",
  "flags": [],
  "evidence": [...],
  "raw_data": {
    "monthly_income": 150000,
    "property_value": 8000000,
    "employment_type": "salaried",
    "proposed_emi": 19700.0,
    "declared_existing_emis": 5000.0,
    "foir_threshold": 0.55,
    "assumed_annual_interest_rate_percent": 8.5
  }
}
```

`cibil_score`, `credit_risk_tier`, `foir`, `monthly_obligations`, `ltv`, `income_stability`, `confidence`, `flags`, `evidence`, and `raw_data` are the fields already consumed by `app.decision.risk_engine` and `app.agents.decision.crew` (see `README_decision.md`'s Input Contracts section) - this branch does not change their meaning or shape. `credit_band`, `risk_score`, `preliminary_decision`, and `reasoning` are new, additive fields on the same model that the Decision Agent does not currently read, but are available for audit/report use once wired in.

`raw_data.monthly_income` and `raw_data.property_value` are read by `app.decision.contradiction_detector` for cross-agent consistency checks - keep those two keys if you change `raw_data`'s shape.

---

## CIBIL Bands

| Score | Band | Risk Tier |
|---|---|---|
| 750-900 | Excellent | low |
| 700-749 | Good | low |
| 650-699 | Fair | moderate |
| 550-649 | Poor | high |
| 300-549 | Very Poor | high |
| No history (NA) | New-to-Credit | moderate |

`None`/no-history is a distinct, valid outcome - not an error - and is treated as risk-neutral, not adverse.

---

## FOIR

```
FOIR = (declared existing EMIs + credit-card EMI-equivalent + proposed EMI) / monthly net income
```

- **Thresholds:** salaried ≤ 55%, self-employed/business ≤ 45% (self-employed income is less stable/verifiable, per common Indian bank practice).
- **Credit-card EMI-equivalent:** an outstanding balance with no declared EMI still counts as an obligation, approximated as 5% of the outstanding balance (the standard minimum-due assumption).
- **Proposed EMI** is computed with the standard reducing-balance formula (`app.credit.foir.calculate_emi`) at a placeholder rate (`credit_config.yaml::foir.assumed_annual_interest_rate_percent`, default 8.5%) - replace with the actual sanctioned rate once loan pricing reaches this agent.

---

## LTV

```
LTV = loan_amount / borrower-declared property_value
```

A preliminary check only - `None` if no property value is declared yet.

---

## Red Flags

| Flag | Trigger | Severity |
|---|---|---|
| Settled account(s) | `settled_accounts > 0` | Severe |
| Written-off account(s) | `written_off_accounts > 0` | Severe |
| DPD exceeding 90 days | `max_dpd_last_12_months > 90` | Severe |
| Possible loan stacking | `recent_enquiries_last_90_days >= 3` | Mild |
| Income-to-loan mismatch | `loan_amount > (6x salaried / 5x self-employed) annual income` | Mild |

Severity is used by `compute_credit_risk_score` (heavier penalty) and `generate_preliminary_decision` (2+ severe flags force a reject).

---

## Income Stability

Matches `app.decision.risk_engine._score_stability`'s expected vocabulary exactly:

| Employment Type | Clean Credit History | 1+ Severe Red Flag |
|---|---|---|
| Salaried | `stable` | `unstable` |
| Self-employed / Business | `moderately_stable` | `unstable` |

---

## Composite Risk Score

`app.credit.scoring.compute_credit_risk_score` - a 0-100 composite, higher = lower risk. This is the Credit Analysis Agent's **own** internal score, distinct from (and one input into) the Decision Agent's separate 6-component `app.decision.risk_engine`, which reads this agent's `cibil_score` / `credit_risk_tier` / `foir` / `ltv` / `income_stability` directly rather than this number.

| Component | Weight |
|---|---|
| Credit band | 45% |
| FOIR headroom | 35% |
| Red flags | 20% |

FOIR headroom scores 100 at FOIR=0, 50 exactly at the employment type's threshold, and falls off linearly past it. Red flags subtract 30 points (severe) or 12 points (mild) each from a 100-point baseline.

---

## Confidence

How reliable *this specific assessment* is (evidence quality), not the borrower's creditworthiness - same meaning as `confidence` elsewhere in this system (`app.decision.confidence`).

```
confidence = 0.90
           - 0.30 if no credit history (cibil_score is None)
           - 0.05 per red flag
           floor 0.30, ceiling 1.0
```

---

## Preliminary Decision Rules

`app.credit.scoring.generate_preliminary_decision` - checked in this order:

```
1. cibil_score < 550 AND no compensating factor        -> REJECT
   (compensating factor: FOIR >= 10pts under threshold AND zero red flags)
2. FOIR exceeds threshold by more than 15 percentage points -> REJECT
3. 2 or more severe red flags                            -> REJECT
4. FOIR over threshold (but not enough to hit rule 2)     -> CONDITIONAL
5. Any red flag present                                   -> CONDITIONAL
6. credit_band == New-to-Credit                            -> CONDITIONAL
7. Otherwise                                                -> APPROVE
```

**This is the only place the decision is made.** `run_credit_reasoning` (the LLM step) explains the result of this function - it is never asked to choose, and its prompt explicitly forbids overriding it.

---

## LLM Reasoning

`app.agents.credit.crew.run_credit_reasoning` builds a deterministic plain-language explanation of the already-final assessment (2-4 sentences from CIBIL band, FOIR, LTV and flags). It uses no LLM and cannot fail.

`_build_credit_summary` (the prompt's structured input) is a pure function, unit-tested directly in `test_credit_crew.py` without invoking a real LLM - same pattern as `test_crew.py` for the Decision Agent.

---

## Configuration

**File:** `backend/config/credit_config.yaml`

```yaml
cibil:
  bands: {excellent: 750, good: 700, fair: 650, poor: 550}
  risk_tier_map: {excellent: low, good: low, fair: moderate, poor: high, very_poor: high, new_to_credit: moderate}

foir:
  thresholds: {salaried: 0.55, self_employed: 0.45, business: 0.45}
  credit_card_emi_equivalent_rate: 0.05
  assumed_annual_interest_rate_percent: 8.5

red_flags:
  loan_stacking_enquiry_threshold: 3
  income_to_loan_multiple: {salaried: 6, self_employed: 5, business: 5}

decision:
  cibil_hard_reject_threshold: 550
  foir_reject_overshoot: 0.15
  compensating_foir_headroom: 0.10

risk_score:
  weights: {credit_band: 0.45, foir: 0.35, red_flags: 0.20}
  red_flag_penalty: {severe: 30.0, mild: 12.0}

confidence:
  base: 0.90
  no_credit_history_penalty: 0.30
  per_red_flag_penalty: 0.05
  floor: 0.30
```

If the file is missing, `app.credit.config.get_credit_config` falls back to identical in-code defaults, so tests and a fresh checkout work without it.

---

## KYC / PAN Note

This agent never receives, stores, prints, or logs raw PAN/Aadhaar numbers. KYC identity verification is the Document Ingestion Agent's responsibility (`document_analysis.kyc`); this agent only consumes financial fields off `borrower_profile`. If a future real credit bureau integration needs PAN to perform the pull, fetch it from the secure document store by `application_id` at call time in `app.services.credit_bureau` - never place it on `UnderwritingState`.

---

## What's Stubbed

- **`app.services.credit_bureau.fetch_credit_report`** - returns a deterministic mock report (hash of `application_id`) so the agent runs end-to-end with zero external credentials. `# TODO: replace with a real CIBIL / Experian / Equifax / CRIF High Mark API call.`
- **`state["credit_bureau_data"]`** - an optional override on `UnderwritingState` (additive field) that bypasses the stub. Tests always set this explicitly for determinism; a future real integration can populate it the same way instead of editing the node.
- **`assumed_annual_interest_rate_percent`** - a placeholder EMI rate (8.5%) used to estimate the proposed EMI before a real sanctioned rate is available from the product/decision layer.

Everything else - CIBIL band mapping, FOIR (incl. credit-card min-due-as-EMI logic), LTV, red-flag detection, income stability, the composite risk score, and the REJECT/CONDITIONAL/APPROVE rules - is real, deterministic Python.

---

## Tests

```bash
cd backend
pytest tests/test_credit_*.py -v
```

| File | Covers |
|---|---|
| `test_credit_cibil.py` | Band boundaries, no-history handling, risk-tier mapping |
| `test_credit_foir.py` | EMI formula, FOIR + credit-card equivalent, threshold lookup |
| `test_credit_ltv.py` | LTV calculation, no-property-value case |
| `test_credit_red_flags.py` | All five red-flag triggers, severity counting |
| `test_credit_stability.py` | Stability classification by employment type + flags |
| `test_credit_scoring.py` | All decision-rule branches, confidence bounds, risk score bounds |
| `test_credit_crew.py` | Summary builder content (no real LLM call) |
| `test_credit_node.py` | Full node - salaried approve, self-employed FOIR reject, NA-history conditional, red-flag reject, missing-data error path, LTV wiring (LLM reasoning monkeypatched) |

---

## Disclaimer

This is a decision-support/pre-screening output, consistent with the rest of this system (see `README_decision.md`). `preliminary_decision` is this agent's own credit-specific call, not a final lending decision - the Decision Agent's independent risk engine, contradiction checks, and rule-based crew still run on top of it. Prototype thresholds and weights here are engineering choices, not official RBI/lender regulatory requirements.
