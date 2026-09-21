# Mortgage Underwriting System

**Agentic AI Mortgage Underwriting System — Backend**

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

**Pipeline:** Geocode → Local Comparables DB → Mock External API → Reconcile → Explain  
**Sources:** Nominatim geocoder, local `data/dummy_properties.csv`, mock AVM API

---

### 4. Compliance Agent (`app/graph/nodes/compliance.py`)
**Placeholder** — Returns PASS for KYC/CDD, PMLA, RBI Fair Practices  
**TODO:** Teammate to implement KYC/CDD, PMLA source-of-funds, RERA, NHB, critical flag detection

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
| Data | pandas (comparables CSV) |
| Testing | pytest (98 tests) |
| **No external LLMs** — Fully deterministic, zero API keys required |

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
│   │   ├── graph/
│   │   │   ├── nodes/                  # LangGraph nodes
│   │   │   │   ├── credit.py, decision.py, property_valuation.py
│   │   │   │   ├── compliance.py, doc_ingestion_to_analysis.py
│   │   │   ├── state.py, workflow.py   # State & graph definition
│   │   ├── models/                     # Pydantic models
│   │   │   ├── decision.py, document_ingestion.py, document_ingestion_state.py
│   │   │   └── property_valuation.py
│   │   ├── tools/                      # Shared utilities
│   │   │   ├── comparables_db.py, external_api.py, geocoder.py
│   │   ├── services/credit_bureau.py   # Stub (replace with real API)
│   │   ├── config/risk_config.yaml     # Decision thresholds
│   │   └── main.py                     # FastAPI entrypoint
│   ├── tests/                          # 98 tests (unit + e2e)
│   │   ├── test_*.py, conftest.py, mock_data/generate_docs.py
│   ├── data/dummy_properties.csv       # Property comparables
│   ├── pyproject.toml
│   └── README.md
└── .codegraph/PIPELINE.md              # This file
```

---

## 🚀 Quick Start

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest tests/ -v           # 98 tests pass
python smoke_test_pipeline.py  # Full pipeline with mock PDFs
uvicorn app.main:app --reload  # Start API server
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/underwriting/{application_id}/run` | Execute full pipeline |
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
| **Total** | **98** | **100%** |

---

## 🔑 Key Design Decisions

1. **Zero LLM Dependencies** — All decisions deterministic; LLM only for explanations with graceful fallback
2. **Parallel Execution** — Credit, Property, Compliance run simultaneously via LangGraph fan-out
3. **Annotated State** — `errors` uses `Annotated[list, operator.add]` for concurrent writes
4. **Transformation Node** — Bridges `doc_ingestion_output` → `document_analysis` format
5. **Hard Safety Gates** — Decision finalizer overrides any crew recommendation
6. **Evidence Provenance** — Every field traces back to source agent/document
6. **Test Fixtures** — 4 realistic Indian mortgage scenarios (clean, name discrepancy, salary discrepancy, missing docs)

---

## 📋 Configuration

`backend/app/config/risk_config.yaml`:
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
