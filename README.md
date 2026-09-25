# Mortgage Underwriting System

**Agentic AI Mortgage Underwriting System — Backend (`backend/`) + Next.js Frontend (`frontend/`)**

A fully autonomous, deterministic mortgage underwriting pipeline built with LangGraph that chains four specialized agents in parallel: Document Ingestion → (Credit Analysis + Property Valuation + Compliance) → Decision Agent.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MORTGAGE UNDERWRITING PIPELINE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /underwriting/{id}/run                                                │
│        │                                                                     │
│        ▼                                                                     │
│  ┌─────────────────┐                                                         │
│  │ Document        │  7-step ingestion: Classify → Preprocess → Extract     │
│  │ Ingestion       │  → Validate → Reconcile → Confidence → HITL           │
│  └────────┬────────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │ Credit          │     │ Property        │     │ Compliance      │       │
│  │ Analysis        │     │ Valuation       │     │ Agent           │       │
│  │ (Parallel)      │     │ (Parallel)      │     │ (Parallel)      │       │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘       │
│           │                       │                       │                │
│           └───────────────────────┼───────────────────────┘                │
│                                   ▼                                        │
│                        ┌─────────────────┐                                 │
│                        │ Decision Agent  │  8-step: Validate → Contradict  │
│                        │                 │  → Compare → Risk → Confidence  │
│                        │                 │  → Crew → Finalize → Report     │
│                        └────────┬────────┘                                 │
│                                 │                                          │
│                    ┌────────────┴────────────┐                            │
│                    ▼                         ▼                            │
│             ┌─────────────┐           ┌─────────────┐                    │
│             │ Human       │           │ Final       │                    │
│             │ Review      │           │ Report      │                    │
│             └─────────────┘           └─────────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Four Core Agents

### 1. Document Ingestion Agent (`app/document_ingestion/`)
**Input:** Raw PDF paths (`raw_document_paths`)  
**Output:** `doc_ingestion_output` (rich `DocumentIngestionOutput`)

**7-Step Pipeline:**
1. **Classification** — Multi-signal pattern scoring for Indian mortgage docs (PAN, Aadhaar, Salary Slip, Form 16, ITR, Bank Statement, Property Deed)
2. **Preprocessing** — PyMuPDF text/layout extraction, table detection
3. **Structured Extraction** — Pydantic entities with field-level provenance
4. **Validation** — PAN checksum, Aadhaar Verhoeff, IFSC, salary arithmetic
5. **Cross-Document Reconciliation** — Fuzzy name matching, income vs bank credits, employer consistency, address verification
6. **Confidence Scoring** — Multi-dimensional breakdown, mandatory document checklist
7. **HITL Routing** — Human review triggers based on confidence thresholds

**Key Models:** `BorrowerKYCProfile`, `BorrowerIncomeProfile`, `BorrowerLiabilitiesProfile`, `PropertyProfile`

---

### 2. Credit Analysis Agent (`app/credit/`)
**Input:** `borrower_profile` (monthly_income, loan_amount, loan_tenure_months, property_value, existing_debt, employment_type)  
**Output:** `credit_analysis` (`CreditAnalysisResult`)

**Deterministic Sub-Modules:**
- `cibil.py` — CIBIL band mapping (Excellent/Good/Fair/Poor/Very Poor/NA)
- `foir.py` — FOIR calculation with employment-type thresholds
- `ltv.py` — Loan-to-Value ratio
- `red_flags.py` — DPD≥90, settled/written-off, loan stacking, income/loan mismatch
- `stability.py` — Income stability assessment (Salaried/Self-employed/Business)
- `scoring.py` — Composite risk score (0-100), preliminary decision (APPROVE/CONDITIONAL/REJECT)

**No LLM** — All rule-based, fully auditable. LLM only used for plain-language explanation (deterministic fallback).

---

### 3. Property Valuation Agent (`app/graph/nodes/property_valuation.py`)
**Input:** Property data from `doc_ingestion_output.property_profile`  
**Output:** `property_analysis` (dict)

**Pipeline:** Geocode → AVnester live listings → Median ₹/sqft × area → Confidence → Explain  
**Sources:** Nominatim geocoder and the live [AVnester](https://www.avnester.com) public API (no key needed). There is no local/dummy data.  
**Behaviour:** searches the subject's locality first and widens to the whole city when fewer than 3 usable comparables exist (confidence −0.10). Supports `apartment`, `villa`, `independent_house` and `plot`. **AVnester only covers Tamil Nadu**, and its for-sale inventory is currently mostly plots, so anything else (or an AVnester outage) yields valuation 0 / confidence 0 and a SUSPEND for human review.

---

### 4. Compliance Agent (`app/compliance/`, `app/graph/nodes/compliance.py`)
**Input:** `borrower_profile`, `document_analysis` (KYC / identity), `property_analysis` (RERA status, under-construction flag)
**Output:** `compliance_analysis` (`ComplianceAnalysisResult`) — feeds Gate #1 of the Decision Agent

**Design rule:** the LLM only explains, never decides. `rule_status` and `critical_flags` always come from the deterministic rules engine; the crew wrapper (`app/agents/compliance/crew.py`) has a template fallback and never raises.

| Check | Module | Critical (blocks decision) | Non-critical |
|-------|--------|----------------------------|--------------|
| KYC completeness | `kyc_checks.py` | Missing/invalid required document | — |
| Identity consistency | `identity_consistency.py` | PAN number mismatch | Name mismatch = warning; minor formatting passes; missing data is not a mismatch |
| PMLA / AML | `pmla_aml.py` | Missing source-of-funds declaration | Missing identity log = warning |
| RBI fair practices | `rbi_fair_practices.py` | Protected attribute used (case-insensitive, multiple detected) | — |
| NHB priority sector | `nhb_priority_sector.py` | — | Above metro ceiling = not eligible (not critical); missing data does not classify |
| RERA | `rera_check.py` | Under construction and not registered | N/A if not under construction; can be disabled via config |

`rules_engine.py` runs all checks and applies config toggles; `flags.py` / `scoring.py` produce severity-graded flags and a confidence score (penalties, floor, cap). Thresholds, protected attributes and rule switches live in `config/compliance_config.yaml`.

---

### 5. Decision Agent (`app/decision/`, `app/graph/nodes/decision.py`)
**Input:** All four upstream outputs  
**Output:** `decision` (`DecisionResult`), `underwriting_report` (`UnderwritingReport`)

**8-Step Pipeline:**
1. **Input Validation** — Checks all required upstream keys present
2. **Contradiction Detection** — Cross-agent field conflicts (income, property value, identity)
3. **Agent Comparison** — Confidence & assessment alignment across agents
4. **Risk Scoring** — 6-component weighted score (credit, property, compliance, borrower, doc quality, contradiction)
5. **Confidence Assessment** — Composite confidence with factor breakdown
6. **Deterministic Crew** — Three role-based outputs (Underwriter, Risk Analyst, Report Writer) — **no LLM**
7. **Deterministic Finalization** — Hard safety gates (compliance, contradictions, confidence) → score-based APPROVE/DENY/SUSPEND
8. **Report Generation** — Evidence-backed, audit-ready underwriting report

**Safety Gates (override crew):**
- Critical compliance flag → SUSPEND
- Unresolved critical contradiction → SUSPEND
- Confidence < threshold (0.85) → SUSPEND
- Material crew disagreement → SUSPEND

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph (StateGraph) |
| Validation | Pydantic v2 |
| API | FastAPI + Uvicorn |
| PDF Processing | PyMuPDF (fitz), pdfplumber |
| NLP/Extraction | Regex + deterministic parsers |
| Geocoding | geopy (Nominatim) |
| Data | pandas (comparables CSV), rapidfuzz (identity matching) |
| Frontend | Next.js + Tailwind (`frontend/`, pnpm) |
| Testing | pytest (156 tests) |
| Explanations | Optional **local LLM (Ollama)**, phrasing only; every decision is rule-based. No API keys. |

---

## 📁 Project Structure

```
mortgage-underwriting-system/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── credit/crew.py          # Deterministic credit reasoning
│   │   │   └── decision/crew.py        # Deterministic decision crew
│   │   ├── credit/                     # Credit analysis sub-modules
│   │   │   ├── cibil.py, foir.py, ltv.py, red_flags.py, stability.py, scoring.py
│   │   ├── decision/                   # Decision agent sub-modules
│   │   │   ├── input_validator.py, contradiction_detector.py, agent_comparator.py
│   │   │   ├── risk_engine.py, confidence.py, finalizer.py, report_writer.py
│   │   ├── document_ingestion/         # 7-step ingestion pipeline
│   │   │   ├── agent.py, classifier.py, extractors.py, validators.py
│   │   │   ├── reconciliation.py, confidence.py, preprocessor.py
│   │   ├── compliance/                 # KYC, identity, PMLA, RBI, NHB, RERA rules + engine
│   │   ├── graph/
│   │   │   ├── nodes/                  # LangGraph nodes
│   │   │   │   ├── credit.py, decision.py, property_valuation.py
│   │   │   │   ├── compliance.py, doc_ingestion_to_analysis.py
│   │   │   ├── state.py, workflow.py   # State & graph definition
│   │   ├── models/                     # Pydantic models
│   │   │   ├── decision.py, document_ingestion.py, document_ingestion_state.py
│   │   │   └── property_valuation.py
│   │   ├── tools/                      # Shared utilities
│   │   │   ├── external_api.py (AVnester valuation), geocoder.py
│   │   ├── services/credit_bureau.py   # Stub (replace with real API)
│   │   ├── config/risk_config.yaml     # Decision thresholds
│   │   └── main.py                     # FastAPI entrypoint
│   ├── config/                         # risk_, credit_, compliance_config.yaml
│   ├── tests/                          # 156 tests (unit + e2e)
│   │   ├── test_*.py, conftest.py, mock_data/generate_docs.py
│   ├── pyproject.toml
│   └── README.md
├── frontend/                           # Next.js UI (app/, components/, lib/, public/)
└── .codegraph/PIPELINE.md              # This file
```

---

## ⚙️ Environment

Copy `backend/.env.example` to `backend/.env` (loaded automatically at startup). No secret is required: the AVnester public API needs no key. **Local LLM:** with [Ollama](https://ollama.com) running (`ollama pull llama3.2`), `LLM_PROVIDER=ollama` makes the compliance and property agents write their explanations with it (a run then takes ~5-15 s instead of ~1 s). Set `LLM_PROVIDER=none` to always use the fixed templates. If AVnester has no listings for a locality (or is unreachable), valuation confidence drops to 0 and the decision is SUSPENDed for human review.

---

## 🗄️ Database (PostgreSQL)

Set `DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/mortgage_uw` in `backend/.env`. On startup the backend creates the database (if missing) and these tables: `applications` (full result as JSONB), `review_items`, and `documents` (the uploaded PDFs, so a human reviewer can open them from the UI). `GET /health` reports `"storage": "postgres"` or `"memory"`. With `DATABASE_URL` empty, or if Postgres is unreachable, the app falls back to in-memory storage and logs an error. Tests always use memory; run the Postgres round-trip test with `TEST_DATABASE_URL` pointing at a throwaway database.

---

## 🧠 Do the agents need an LLM?

**No.** Every decision and number comes from rules and data; an LLM only rephrases the explanation text.

| Agent | How it works | LLM? |
|-------|--------------|------|
| Document Ingestion | Regex / rule-based extraction, validators and reconciliation | Never |
| Credit | Rules for CIBIL band, FOIR, LTV, red flags, then a composite score; fixed explanation text | Never |
| Property | Live AVnester listings → median ₹/sq ft × area; confidence from comparable count | Optional: only the 2-3 sentence explanation |
| Compliance | Deterministic rules engine (KYC, identity, PMLA, RBI, NHB, RERA) | Optional: only the explanation |
| Decision | 6-component weighted risk engine, contradiction checks, hard safety gates; rule-based crew and report | Never (must stay repeatable and auditable) |

The optional LLM is a **local Ollama model** (no API key, nothing leaves your machine). CrewAI has been removed. Any explanation that mentions a verdict (approve / deny / reject / suspend / decline / recommend / eligible) is discarded, and any failure (Ollama off, timeout) falls back to the fixed template. With the LLM on, a run takes ~5-15 s instead of ~1 s. Set `LLM_PROVIDER=none` in `backend/.env` to turn it off.

---

## 🚀 Quick Start

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest tests/ -v           # 156 tests pass
python smoke_test_pipeline.py  # Full pipeline on the 4 mock-document scenarios (prints each result)
uvicorn app.main:app --reload  # Start API server
```

**Show the mock-document results**

| How | Command / action | What you see |
|-----|------------------|--------------|
| Terminal (quickest) | `cd backend` then `.env\Scripts\python.exe smoke_test_pipeline.py` | Each scenario's documents, CIBIL/FOIR/LTV, live valuation, compliance flags, decision and rationale, ending in `SMOKE TEST PASSED` |
| Browser | Start backend + frontend, open http://localhost:3000, **New application** → pick a demo scenario | The full workflow, agent reports, review queue and final report |

Expected results: **clean → APPROVE** (risk 88), **name mismatch / salary mismatch / missing documents → SUSPEND** (human review). The mock PDFs are generated into `backend/mock_documents/` by `tests/mock_data/generate_docs.py`.

**Frontend:**
```bash
cd frontend
pnpm install                   # or: npx pnpm@10 install
pnpm dev                       # http://localhost:3000, proxies /api/v1/* to 127.0.0.1:8000
```
Start the backend first (`uvicorn app.main:app --port 8000`).

---

## 🖥️ Running the full stack

```bash
cd backend  && .env\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend && npx pnpm@10 dev          # http://localhost:3000
```

In the UI, **New application** accepts real PDFs (or one of four demo scenarios) and runs the whole pipeline: ingestion → credit + property + compliance → decision. Results appear on the dashboard, the application's workflow page, per-agent reports, the human-review queue and the final report. Applications, review items and the uploaded PDFs are stored in PostgreSQL (see below).

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/underwriting/run` | **Full pipeline from uploaded PDFs** (multipart) or `demo_scenario` |
| GET | `/api/v1/applications`, `/api/v1/applications/{id}` | Stored results (agents, report, review items) |
| GET | `/api/v1/applications/{id}/documents/{doc_id}` | Stored source PDF (inline) |
| GET/POST | `/api/v1/review-items`, `/api/v1/review-items/{id}/resolve` | Human-review queue |
| GET | `/api/v1/demo-scenarios` | Bundled demo borrowers |
| POST | `/underwriting/{application_id}/run` | Execute full pipeline (server-side file paths) |
| POST | `/document-ingestion/process` | Document ingestion only |
| POST | `/property-valuation/estimate` | Property valuation only |
| GET | `/health` | Health check |

**Request Body (run):**
```json
{
  "application_id": "APP-001",
  "raw_document_paths": ["path/to/pan.pdf", "path/to/salary.pdf"],
  "borrower_profile": {
    "name": "Priya Sharma",
    "monthly_income": 150000,
    "employment_type": "Salaried",
    "loan_amount": 5000000,
    "loan_tenure_months": 240,
    "property_value": 7500000,
    "existing_debt": 10000
  }
}
```

---

## 🧪 Test Coverage

| Category | Tests | Coverage |
|----------|-------|----------|
| Credit (CIBIL, FOIR, LTV, Red Flags, Scoring, Stability) | 27 | 100% |
| Document Ingestion (Validators, 4 Scenarios, LangGraph Node) | 16 | 100% |
| Decision (Finalizer, Risk Engine, Contradictions, Comparator, Confidence) | 19 | 100% |
| E2E Pipeline (APPROVE, DENY, SUSPEND, Compliance Gate) | 8 | 100% |
| Compliance (6 rule modules, scoring, crew, node) | 43 | 100% |
| Pipeline regressions (graph, AVnester valuation, compliance mapping, scenario 1 APPROVE) | 10 | 100% |
| **Total** | **156** | **100%** |

---

## 🔑 Key Design Decisions

1. **Rule-based decisions, local-LLM explanations** — every decision is deterministic. The compliance and property agents optionally ask a local Ollama model to phrase their explanation; text that mentions a verdict is rejected, and any failure falls back to a fixed template
2. **Parallel Execution** — Credit, Property, Compliance run simultaneously via LangGraph fan-out
3. **Annotated State** — `errors` uses `Annotated[list, operator.add]` for concurrent writes
4. **Transformation Node** — Bridges `doc_ingestion_output` → `document_analysis` format
5. **Hard Safety Gates** — Decision finalizer overrides any crew recommendation
6. **Evidence Provenance** — Every field traces back to source agent/document
6. **Test Fixtures** — 4 realistic Indian mortgage scenarios (clean prime: Coimbatore residential plot priced live from AVnester; name discrepancy; salary discrepancy; missing docs)

---

## 📋 Configuration

`backend/config/risk_config.yaml` (also `credit_config.yaml`, `compliance_config.yaml`):
```yaml
decision:
  approve_min_score: 80
  deny_max_score: 40
  minimum_confidence: 0.85
credit:
  foir:
    assumed_annual_interest_rate_percent: 9.5
```

---

## 🤝 Contributing

1. All new logic must be deterministic and testable
2. Add unit tests for new credit/decision rules
3. Run `pytest tests/ -v` before committing
4. Update `.codegraph/PIPELINE.md` for architectural changes

---
