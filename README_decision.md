# Decision Agent

The Decision Agent is the final stage of the Mortgage Underwriting System — a decision-support/pre-screening system for Indian housing finance. It synthesizes outputs from four upstream agents (Document Ingestion, Credit Analysis, Property Valuation, Compliance), applies deterministic risk scoring, runs a CrewAI-based multi-agent reasoning crew, and produces an evidence-backed `APPROVE`, `DENY`, or `SUSPEND` recommendation.

**Core principle: Deterministic rules decide; LLMs explain and synthesize.**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Internal Pipeline](#internal-pipeline)
3. [Module Layout](#module-layout)
4. [LangGraph State](#langgraph-state)
5. [Input Contracts](#input-contracts)
6. [Input Validator](#input-validator)
7. [Contradiction Detector](#contradiction-detector)
8. [Agent Comparator](#agent-comparator)
9. [Risk Engine](#risk-engine)
10. [Confidence Engine](#confidence-engine)
11. [CrewAI Decision Crew](#crewai-decision-crew)
12. [Deterministic Finalizer](#deterministic-finalizer)
13. [Report Writer](#report-writer)
14. [FastAPI Endpoints](#fastapi-endpoints)
15. [Configuration](#configuration)
16. [Pydantic Models](#pydantic-models)
17. [Audit and HITL](#audit-and-hitl)
18. [Error Handling](#error-handling)
19. [Tests](#tests)
20. [Architectural Invariants](#architectural-invariants)

---

## Architecture Overview

```text
Next.js UI
    |
    v
FastAPI  ---->  POST /underwriting/{id}/run
    |
    v
LangGraph (state + orchestration)
    |
    v
Decision Node
    |
    v
    +-- Input Validator
    +-- Contradiction Detector
    +-- Agent Comparator
    +-- Deterministic Risk Engine
    +-- Confidence Engine
    +-- CrewAI Decision Crew (Underwriter / Risk Analyst / Report Writer)
    +-- Deterministic Finalizer
    +-- Report Writer
    |
    +---------+---------+
  APPROVE     DENY     SUSPEND
                       |
                       v
                  Human Review
                       |
                       v
                  Report + Audit
```

The Decision Agent does not interact with raw documents. It consumes **structured dict outputs** from upstream agents passed through the shared LangGraph state.

---

## Internal Pipeline

Each run follows a fixed, ordered pipeline inside the decision node (`backend/app/graph/nodes/decision.py`):

```
1. validate_inputs(state)           --> ValidationResult
2. detect_contradictions(state)     --> list[Contradiction]
3. compare_agents(state)            --> AgentComparison
4. calculate_risk_score(...)        --> RiskAssessment
5. calculate_confidence(...)        --> ConfidenceAssessment
6. run_decision_crew(...)           --> DecisionCrewOutput
7. deterministic_finalize(...)      --> DecisionResult
8. generate_report(...)             --> UnderwritingReport
```

Each stage stores its output back into `UnderwritingState`. If input validation fails at step 1, the pipeline short-circuits to an immediate `SUSPEND` — no further stages execute.

---

## Module Layout

```
backend/
├── config/
│   └── risk_config.yaml                # Risk weights, bands, thresholds, LLM config
├── app/
│   ├── main.py                         # FastAPI endpoints
│   ├── agents/
│   │   └── decision/
│   │       └── crew.py                 # CrewAI agents, tasks, crew
│   ├── decision/
│   │   ├── input_validator.py          # Required-field validation
│   │   ├── contradiction_detector.py   # Cross-agent field comparison
│   │   ├── agent_comparator.py         # Assessment/confidence comparison
│   │   ├── risk_engine.py              # Deterministic 6-component risk scoring
│   │   ├── confidence.py               # Deterministic confidence calculation
│   │   ├── finalizer.py                # Authoritative safety gates + final decision
│   │   └── report_writer.py            # 15-section underwriting report
│   ├── graph/
│   │   ├── state.py                    # UnderwritingState TypedDict
│   │   ├── workflow.py                 # LangGraph StateGraph definition
│   │   └── nodes/
│   │       └── decision.py             # decision_node entry point
│   ├── models/
│   │   └── decision.py                 # All Pydantic models/enums
│   ├── tools/
│   │   └── policy_validator.py         # CrewAI tools (risk, confidence, policy)
│   └── services/
│       ├── audit.py                    # In-memory audit store
│       ├── llm.py                      # LLM provider configuration
│       └── report.py                   # Report JSON export
└── tests/
    ├── conftest.py                     # 4 synthetic test cases
    ├── test_input_validator.py
    ├── test_contradiction_detector.py
    ├── test_agent_comparator.py
    ├── test_risk_engine.py
    ├── test_confidence.py
    ├── test_crew.py
    ├── test_finalizer.py
    ├── test_report_writer.py
    └── test_e2e_pipeline.py
```

---

## LangGraph State

Defined in `backend/app/graph/state.py` as `UnderwritingState(TypedDict, total=False)`:

| Field | Type | Purpose |
|---|---|---|
| `application_id` | `str` | Unique application identifier |
| `borrower_profile` | `dict` | Applicant details (name, income, loan, property, etc.) |
| `documents` | `list[dict]` | Submitted documents |
| `document_analysis` | `dict` | Upstream Document Agent output |
| `credit_analysis` | `dict` | Upstream Credit Agent output |
| `property_analysis` | `dict` | Upstream Property Agent output |
| `compliance_analysis` | `dict` | Upstream Compliance Agent output |
| `validation_result` | `dict` | Input validation result |
| `contradictions` | `list[dict]` | Detected cross-agent contradictions |
| `agent_comparison` | `dict` | Agent assessment comparison |
| `risk_assessment` | `dict` | Deterministic risk score/components |
| `confidence_assessment` | `dict` | Confidence score/factors |
| `decision_crew_output` | `dict` | CrewAI crew output |
| `decision` | `dict` | Final `DecisionResult` |
| `underwriting_report` | `dict` | Structured report |
| `human_review_required` | `bool` | HITL flag |
| `audit_record` | `dict` | Audit trail entry |
| `errors` | `list[dict]` | Accumulated errors |

The LangGraph workflow (`backend/app/graph/workflow.py`) defines 3 nodes:

- `decision` (entry) → `decision_node`
- Conditional routing: `SUSPEND` decision → `human_review` node; otherwise → `report` node
- `human_review` → `report` → `END`

---

## Input Contracts

The Decision Agent consumes structured dicts from four upstream agents. It does not read raw PDFs or documents.

### Document Analysis

```json
{
  "verification_status": "VERIFIED",
  "documents": [...],
  "income": {"monthly_income": 100000},
  "missing_documents": [],
  "extraction_confidence": 0.92,
  "provenance": [...],
  "contradictions": [...],
  "flags": []
}
```

### Credit Analysis

```json
{
  "cibil_score": 750,
  "credit_risk_tier": "LOW",
  "foir": 0.35,
  "monthly_obligations": 25000,
  "ltv": 0.70,
  "income_stability": "stable",
  "confidence": 0.88,
  "flags": [],
  "evidence": [...],
  "raw_data": {"monthly_income": 95000, "property_value": 5000000}
}
```

### Property Analysis

```json
{
  "estimated_value": 5200000,
  "market_range_low": 4800000,
  "market_range_high": 5600000,
  "valuation_confidence": 0.82,
  "price_per_sqft": 8500,
  "comparables": [...],
  "rera_status": "REGISTERED",
  "valuation_variance_percent": 4.0,
  "flags": [],
  "evidence": [...]
}
```

### Compliance Analysis

```json
{
  "kyc_cdd": {"status": "PASS"},
  "pmla_source_of_funds": {"status": "PASS"},
  "rbi_fair_practices": {"status": "PASS"},
  "critical_flags": [],
  "confidence": 0.90,
  "evidence": [...],
  "rule_status": {...}
}
```

### Borrower Profile

```json
{
  "application_id": "APP-001",
  "name": "Priya Sharma",
  "age": 32,
  "monthly_income": 100000,
  "employment_type": "SALARIED",
  "employer": "TCS",
  "loan_amount": 3500000,
  "loan_tenure_months": 240,
  "property_value": 5000000,
  "existing_debt": 0,
  "cibil_score": 750
}
```

---

## Input Validator

**File:** `backend/app/decision/input_validator.py`

Validates completeness of required inputs before any analysis runs.

**Required keys:** `application_id`, `borrower_profile`, `document_analysis`, `credit_analysis`, `property_analysis`, `compliance_analysis`.

**Behavior:**
- Missing or empty-dict values are flagged as `MISSING` in `upstream_status`
- `is_complete = True` only when all 6 required keys are present and non-empty
- Validation warnings (non-blocking): empty borrower name, non-positive income/loan, >3 missing documents, CIBIL < 300, compliance critical flags

**On failure:** The decision node short-circuits to an immediate `SUSPEND` result (risk_score 0, confidence 0, human_review_required=True) without running any downstream stages.

---

## Contradiction Detector

**File:** `backend/app/decision/contradiction_detector.py`

Cross-checks equivalent fields across agent outputs using dotted-path resolution.

| Field Pair | Tolerance | Severity |
|---|---|---|
| `document_analysis.income.monthly_income` vs `credit_analysis.raw_data.monthly_income` | 10% | HIGH if >30% diff, else MEDIUM |
| `borrower_profile.monthly_income` vs `credit_analysis.raw_data.monthly_income` | 10% | HIGH if >30% diff, else MEDIUM |
| `property_analysis.estimated_value` vs `borrower_profile.property_value` | 5% | HIGH if >20% diff, else MEDIUM |
| `property_analysis.estimated_value` vs `credit_analysis.raw_data.property_value` | 5% | HIGH if >20% diff, else MEDIUM |
| `borrower_profile.cibil_score` vs `credit_analysis.cibil_score` | 5% | Always HIGH |

Additionally, any contradictions already reported by the Document Agent are ingested.

All detected contradictions are marked `UNRESOLVED`. The function `has_unresolved_critical()` returns `True` if any `HIGH` or `CRITICAL` contradiction exists unresolved — this feeds the finalizer's hard safety gate.

**Contradiction format:**
```json
{
  "field": "monthly_income",
  "severity": "HIGH",
  "sources": [
    {"agent": "document", "value": 100000},
    {"agent": "credit", "value": 80000}
  ],
  "resolution": "UNRESOLVED",
  "description": "Income mismatch between document and credit agents"
}
```

---

## Agent Comparator

**File:** `backend/app/decision/agent_comparator.py`

Compares summaries across all four upstream agents and identifies agreement/disagreement.

**Extracted summaries:**
- Credit: cibil, tier, foir, ltv, stability, confidence
- Property: value, valuation_confidence, rera
- Compliance: kyc/pmla/rbi statuses, critical flag count, confidence
- Document: verification status, missing count, extraction confidence

**Agreement checks** (all use <10% relative difference threshold):
- `monthly_income` — document vs credit
- `property_value` — property vs borrower profile
- `ltv` — credit's ltv vs computed `loan_amount / property_value` (<5% absolute)

`material_disagreement = True` if disagreement exists on `monthly_income` OR `property_value`. This feeds the finalizer's crew disagreement gate.

---

## Risk Engine

**File:** `backend/app/decision/risk_engine.py`

A purely deterministic, weight-based scoring system. All weights and thresholds are configurable via `backend/config/risk_config.yaml`.

### Component Weights

| Component | Weight | Data Source |
|---|---|---|
| Credit History | 25% | `cibil_score`, `credit_risk_tier` |
| FOIR | 20% | `foir` (Fixed Obligation to Income Ratio) |
| LTV | 15% | `loan_amount / property_value` |
| Property | 15% | `valuation_confidence`, `rera_status`, `valuation_variance` |
| Documents | 15% | `missing_documents`, `extraction_confidence`, `verification_status` |
| Financial Stability | 10% | `income_stability` |

### Scoring Logic (per component)

**Credit History (0-100):**
- Base 50; CIBIL >= 750 → +30, >= 700 → +20, >= 650 → +5, >= 550 → -10, < 550 → -30
- No score available → -20
- Risk tier: LOW → +10, HIGH → -15

**FOIR (0-100):**
- <= 30% → 95, <= 40% → 80, <= 50% → 60, <= 60% → 35, else 15
- Missing → 50 (neutral)

**LTV (0-100):**
- <= 60% → 95, <= 70% → 80, <= 80% → 60, <= 90% → 35, else 15
- Not calculable → 50 (neutral)

**Property (0-100):**
- Valuation confidence >= 0.8 → 90, >= 0.6 → 70, >= 0.4 → 45, else 20
- RERA registered → +10, not registered → -10
- |variance| > 20% → -15

**Documents (0-100):**
- None missing → 85, <= 2 missing → 60, else 30
- High extraction confidence → +10, low → -10
- Verified → +5

**Financial Stability (0-100):**
- `stable` → 90, `moderately_stable` → 70, `unstable` → 35, `unknown` → 50

### Total Score

```
total_score = sum(component_weight * raw_score)  clamped to [0, 100]
```

### Risk Bands

| Score Range | Risk Level |
|---|---|
| 80 - 100 | LOW |
| 60 - 79 | MODERATE |
| 40 - 59 | HIGH |
| 1 - 39 | VERY HIGH |

### Key Factors

Component factors containing positive keywords (e.g., "high", "good", "stable", "low risk") are bucketed into `key_positive_factors`. Factors with negative keywords go into `key_risk_factors`.

---

## Confidence Engine

**File:** `backend/app/decision/confidence.py`

Deterministic confidence scoring based on evidence quality, completeness, and consistency. **Confidence means evidence reliability — it is NOT probability of repayment or approval.**

### Formula

```
score = base
      + (completeness_fraction * completeness_weight)
      + (upstream_avg_confidence * upstream_confidence_weight)
      + (evidence_fraction * evidence_weight)
      - (high_contradictions * contradiction_penalty)
      - (material_disagreement * disagreement_penalty)
      - (critical_compliance_flags * compliance_penalty)
```

### Defaults (from `risk_config.yaml`)

| Parameter | Value |
|---|---|
| base | 0.50 |
| completeness_weight | 0.25 |
| evidence_weight | 0.20 |
| contradiction_penalty_per_high | 0.10 |
| upstream_confidence_weight | 0.15 |
| disagreement_penalty | 0.10 |
| compliance_penalty_per_flag | 0.05 (max 0.15) |

**Completeness** is the fraction of 5 required keys present (`borrower_profile`, `document_analysis`, `credit_analysis`, `property_analysis`, `compliance_analysis`).

**Evidence** is `min(provenance_count / 10, 1.0)`.

`below_threshold = score < 0.85` (configurable). Below threshold normally triggers `SUSPEND`.

---

## CrewAI Decision Crew

**File:** `backend/app/agents/decision/crew.py`

Three CrewAI agents run sequentially. All output structured JSON with `recommendation`, `confidence`, `reasoning`, `key_factors`, `risks_identified`, and `missing_information`.

### Agents

| Role | Name | Purpose |
|---|---|---|
| Underwriter | Senior Mortgage Underwriter | Primary underwriting reasoning. Reviews the full case independently. |
| Risk Analyst | Independent Risk Analyst | Challenger role. Tests the Underwriter's assumptions, identifies overlooked risks. |
| Report Writer | Report Writer | Communication only. Produces the report structure. Does NOT change the decision. |

### Execution Flow

```
Underwriter (independent) → Risk Analyst (sees UW output) → Report Writer (sees both)
```

All tasks require JSON output. The crew runs via `crew.kickoff()` with `Process.sequential`.

### Failure Handling

If the crew fails (LLM error, parse error, etc.), the pipeline continues with `DecisionCrewOutput(error=...)`. The crew error does **not** trigger `SUSPEND` by itself — it is recorded in errors and the finalizer proceeds with deterministic assessment.

### Available Tools (not yet attached to agents)

Located in `backend/app/tools/policy_validator.py`:
- `RiskCalculatorTool` — passthrough of pre-calculated risk JSON
- `ConfidenceCalculatorTool` — passthrough of pre-calculated confidence JSON
- `PolicyValidatorTool` — validates that APPROVE is not issued when safety gates require SUSPEND

---

## Deterministic Finalizer

**File:** `backend/app/decision/finalizer.py`

The **authoritative** decision gate. The CrewAI crew **cannot** override it.

### Hard Safety Gates (evaluated in order)

```
1. Critical compliance flag present?           → SUSPEND (compliance_status="BLOCKED")
2. Required input data missing?                → SUSPEND
3. Unresolved critical contradiction?          → SUSPEND
4. Confidence below threshold (< 0.85)?       → SUSPEND
5. Material crew disagreement?                 → SUSPEND
6. Risk calculation failed?                    → SUSPEND
```

### Score-Based Finalization (only after all gates pass)

| Condition | Decision | Human Review |
|---|---|---|
| `score >= 80` | **APPROVE** | Not required |
| `score <= 40` AND confidence >= 0.85 | **DENY** | Required |
| `score <= 40` AND confidence < 0.85 | **SUSPEND** | Required |
| `score 41-79` | **SUSPEND** | Required |

### Crew Disagreement Check

Only **Underwriter vs Risk Analyst** recommendations are compared. Report Writer is excluded. If they disagree, the result is `SUSPEND`.

### Denial Safety

A denial is only issued when confidence is sufficient (>= 0.85). Insufficient confidence for denial defaults to `SUSPEND` — the system never denies merely because it is uncertain.

---

## Report Writer

**File:** `backend/app/decision/report_writer.py`

Generates a structured `UnderwritingReport` with 15 sections. The report **never modifies** the final decision.

### Report Sections

| # | Section | Content |
|---|---|---|
| 1 | Application Summary | ID, timestamp, decision |
| 2 | Borrower Summary | Name, age, income, employment, loan details |
| 3 | Document Verification | Status, doc count, missing docs, extraction confidence |
| 4 | Credit Assessment | CIBIL, tier, obligations, stability, flags |
| 5 | FOIR/LTV | FOIR ratio, LTV ratio |
| 6 | Property Valuation | Value, market range, confidence, per-sqft, RERA, comparables |
| 7 | Compliance | KYC/PMLA/RBI statuses, critical flags, confidence |
| 8 | Risk Score | Score, level, all 6 component breakdowns |
| 9 | Confidence | Score, threshold status, reasoning, factors |
| 10 | Positive Factors | Key strengths identified |
| 11 | Risk Factors | Key risks identified |
| 12 | Final Recommendation | Combined rationale from finalizer + crew |
| 13 | Evidence | All supporting evidence references |
| 14 | Human Review Status | REQUIRED / NOT_REQUIRED |
| 15 | Disclaimer | "Decision-support/pre-screening system. Human accountability remains mandatory." |

---

## FastAPI Endpoints

**File:** `backend/app/main.py`

| Method | Path | Description | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/health` | Health check | — | `{"status": "ok"}` |
| `POST` | `/underwriting/{application_id}/run` | Run full decision pipeline | `UnderwritingRequest` | `{application_id, decision, report, human_review_required}` |
| `GET` | `/underwriting/{application_id}/decision` | Get latest decision | — | Stored `DecisionResult` dict |
| `GET` | `/underwriting/{application_id}/report` | Get audit trail | — | `{application_id, audit_records}` |

### Example Request

```json
POST /underwriting/APP-001/run

{
  "application_id": "APP-001",
  "borrower_profile": { ... },
  "document_analysis": { ... },
  "credit_analysis": { ... },
  "property_analysis": { ... },
  "compliance_analysis": { ... }
}
```

### Example Response

```json
{
  "application_id": "APP-001",
  "decision": {
    "decision": "APPROVE",
    "risk_score": 84.0,
    "risk_level": "LOW",
    "confidence": 0.93,
    "key_positive_factors": ["Strong CIBIL score", "Low FOIR", "RERA registered property"],
    "key_risk_factors": [],
    "compliance_status": "PASS",
    "human_review_required": false,
    "rationale": "...",
    "evidence": [...]
  },
  "report": { ... },
  "human_review_required": false
}
```

---

## Configuration

**File:** `backend/config/risk_config.yaml`

```yaml
risk:
  weights:
    credit: 0.25
    foir: 0.20
    ltv: 0.15
    property: 0.15
    documents: 0.15
    stability: 0.10
  bands:
    low: 80
    moderate: 60
    high: 40

decision:
  approve_min_score: 80
  deny_max_score: 40
  minimum_confidence: 0.85

confidence:
  base: 0.50
  completeness_weight: 0.25
  evidence_weight: 0.20
  contradiction_penalty_per_high: 0.10
  upstream_confidence_weight: 0.15

contradiction:
  income_tolerance_percent: 10
  value_tolerance_percent: 5

llm:
  primary:
    provider: google
    model: gemini-2.0-flash
  fallback:
    provider: groq
    model: llama-3.1-70b-versatile
  temperature: 0.2
  max_tokens: 4096
```

**Environment variables** (`backend/.env.example`):

```
PRIMARY_LLM_PROVIDER=google
PRIMARY_LLM_MODEL=gemini-2.0-flash
FALLBACK_LLM_PROVIDER=groq
FALLBACK_LLM_MODEL=llama-3.1-70b-versatile
GOOGLE_API_KEY=your-google-api-key
GROQ_API_KEY=your-groq-api-key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mortgage_uw
RISK_CONFIG_PATH=config/risk_config.yaml
```

---

## Pydantic Models

**File:** `backend/app/models/decision.py`

### Enums

| Enum | Values |
|---|---|
| `DecisionType` | `APPROVE`, `DENY`, `SUSPEND` |
| `RiskLevel` | `LOW`, `MODERATE`, `HIGH`, `VERY_HIGH` |
| `Severity` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `ResolutionStatus` | `RESOLVED`, `UNRESOLVED`, `PENDING_REVIEW` |
| `CrewRole` | `underwriter`, `risk_analyst`, `report_writer` |

### Key Models

| Model | Purpose |
|---|---|
| `Evidence` | Agent-sourced evidence with field, value, source, confidence |
| `ValidationResult` | is_complete, missing_fields, warnings, upstream_status |
| `Contradiction` | field, severity, sources, resolution, description |
| `AgentComparison` | agreement/disagreement fields, material_disagreement, confidence_comparison |
| `RiskComponent` | name, weight, raw_score, weighted_score, factors |
| `RiskAssessment` | score, level, components, key_positive/risk_factors, calculation_failed |
| `ConfidenceAssessment` | score, factors, below_threshold, reasoning |
| `CrewMemberOutput` | role, recommendation, confidence, reasoning, key_factors, risks_identified, missing_information |
| `DecisionCrewOutput` | underwriter, risk_analyst, report_writer, execution_time_seconds, error |
| `DecisionResult` | Full final decision with all fields |
| `UnderwritingReport` | 15-section structured report |
| `AuditRecord` | Complete audit trail entry |

---

## Audit and HITL

### Audit

An in-memory audit store (`backend/app/services/audit.py`) records each decision with:
- Application ID and timestamp
- Final decision and rationale
- Errors encountered
- Human review status

Records are append-only. The store is a singleton dict — replace with PostgreSQL for production.

### Human-in-the-Loop

```
SUSPEND
   |
   v
Human Review (via Next.js UI)
   |
   v
Reviewer evaluates evidence + report
   |
   v
Reviewer action/override
   |
   v
Audit Log (distinguishes AI recommendation from human action)
```

The AI recommendation and human action remain distinguishable in the audit trail.

---

## Error Handling

```
LLM / API / schema / calculation / database failure
                |
                v
          Structured error dict
                |
                v
          Audit / logging
                |
                v
             SUSPEND
                |
                v
           Human Review
```

- Crew errors are caught and recorded but do **not** crash the pipeline
- Risk calculation failures result in `score=0, calculation_failed=True`
- The finalizer treats crew errors as non-fatal informational entries
- **Never** uses unsafe fallbacks like `except: APPROVE`

---

## Tests

**File:** `backend/tests/`

Four synthetic test cases in `conftest.py`:

| Case | ID | Borrower | Expected |
|---|---|---|---|
| Good | APP-001 | Priya Sharma | APPROVE |
| Weak | APP-002 | Rahul Kumar | DENY |
| Suspend | APP-003 | Ananya Patel | SUSPEND (income contradiction) |
| Missing | APP-004 | Incomplete | SUSPEND (missing credit_analysis) |

### Test Coverage

| Test File | What It Covers |
|---|---|
| `test_input_validator.py` | Completeness check, missing field detection, warnings |
| `test_contradiction_detector.py` | Income contradiction, property mismatch, document contradictions |
| `test_agent_comparator.py` | Income/property agreement, material disagreement, confidence keys |
| `test_risk_engine.py` | Score ranges, 6 components, weight sum, bounds |
| `test_confidence.py` | Good case > 0.6, contradiction penalty, bounds |
| `test_crew.py` | Case summary generation, JSON parsing (no real LLM call) |
| `test_finalizer.py` | Gate logic for all decision outcomes, evidence presence |
| `test_report_writer.py` | Report generation, decision unchanged, disclaimer |
| `test_e2e_pipeline.py` | Full deterministic pipeline (no crew) across all 4 cases |

Run tests:
```bash
cd backend
pytest
```

---

## Architectural Invariants

1. **LangGraph orchestrates** — shared state, node sequencing, conditional routing
2. **CrewAI reasons by role** — Underwriter, Risk Analyst, Report Writer
3. **Deterministic logic calculates and finalizes** — Python code, not LLM output
4. **LLM output cannot bypass safety gates** — the finalizer is authoritative
5. **Missing critical data cannot become APPROVE** — validation gate
6. **Material unresolved contradiction cannot become APPROVE** — contradiction gate
7. **Low confidence routes to SUSPEND/HITL** — confidence gate
8. **Critical compliance issues route to SUSPEND** — compliance gate
9. **Material crew disagreement routes to SUSPEND** — disagreement gate
10. **Protected attributes are never underwriting features** — no religion, caste, gender, region
11. **Material decisions are traceable to evidence/configuration** — full audit trail
12. **Prototype thresholds remain configurable** — never described as regulatory requirements
13. **Errors never silently become APPROVE** — explicit safety by design

---

## Technology Stack

| Component | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Orchestration | LangGraph |
| Multi-Agent Reasoning | CrewAI |
| LLM Abstraction | LangChain |
| Data Contracts | Pydantic |
| Configuration | YAML + pydantic-settings |
| Primary LLM | Google Gemini |
| Fallback LLM | Groq |
| Language | Python 3.11+ |
| Testing | pytest + pytest-asyncio |
| Linting | ruff |

---

## Disclaimer

This system is a **decision-support/pre-screening tool**. It does not constitute an autonomous lending authority. All final lending decisions must be reviewed and approved by qualified human underwriters. Prototype weights and thresholds are engineering choices — they are not official RBI/lender regulatory thresholds.
