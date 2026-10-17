# Agent Metrics — implementation

This documents the **Agent Metrics** page itself: the architecture, data flow, every backend endpoint, every frontend component, and how each of the five agents' cards actually computes its numbers. For *what each metric means and why it was chosen*, see the per-agent methodology docs this page is built on top of:

- `DOCUMENT_INGESTION_METRICS.md`
- `CREDIT_METRICS.md`
- `PROPERTY_VALUATION_METRICS.md`

Decision Agent and Compliance Agent have no separate methodology doc — Decision's metrics are simple runtime/operational counts (documented inline below), and Compliance has no evaluation framework at all yet.

## 1. Design principle

Every agent on the page is either **Runnable** (a real benchmark exists, computed from real data, on demand) or **Not available yet** (with the specific reason why). Nothing on this page is ever a fabricated, hand-typed, or simulated number — that distinction mattered enough to this project that an earlier version of `DOCUMENT_INGESTION_METRICS.md` had to be rewritten after a contributor's benchmark turned out to hardcode its "results" instead of computing them. This page exists partly to make that mistake structurally hard to repeat: a card is either wired to code that runs the real agent, or it says in plain words why it isn't.

Concretely, this means:
- **Runnable** cards never run automatically — nothing is computed on page load. Each has a "Run benchmark" / "Run again" button, because every runnable benchmark does real work (runs the real agent, queries the real database) and that cost should be visible and opt-in, not hidden behind a page visit.
- **Unavailable** cards state the concrete, structural reason (usually: "this needs ground-truth data this system doesn't capture yet"), not a vague "coming soon."
- A metric that can't be computed honestly returns `{"available": false, "reason": "..."}` from the backend rather than a zero or `null` that could be misread as a real result. This pattern appears in `app.credit.metrics.outcome_report` (which predates this page) and was carried into `app.property_valuation.metrics.valuation_accuracy_report`.

## 2. Backend architecture

### 2.1 The overview endpoint

```
GET /api/v1/metrics/overview
```

Returns the static `AGENT_METRICS_STATUS` list defined in `backend/app/main.py` — one entry per agent:

```python
{
    "agent": "document_ingestion",       # key the frontend switches on
    "label": "Document Ingestion Agent", # display name
    "status": "runnable",                # "runnable" | "unavailable"
    "description": "...",                # plain-English explanation shown on the card
    "endpoint": "/api/v1/metrics/document-ingestion",  # null if unavailable
    "method": "POST",                                   # null if unavailable
}
```

The frontend fetches this once when the page loads and renders one card per entry, in list order: Document Ingestion → Decision → Credit → Property → Compliance. Nothing here computes a metric — it's purely routing/descriptive metadata so the frontend doesn't need agent-specific knowledge baked in beyond which `underwritingService` method to call.

### 2.2 The four per-agent endpoints

| Agent | Endpoint | Method | Backend module | Source of data |
|---|---|---|---|---|
| Document Ingestion | `/api/v1/metrics/document-ingestion` | POST | `app.document_ingestion.benchmark.run_bundled_demo_benchmark()` | Runs the **real agent** against 6 bundled demo document sets generated on the fly |
| Decision | `/evaluation/runtime` | GET | `app.evaluation.evaluator.runtime_metrics_from_decisions()` | Reads `app.services.audit.audit_store` (in-memory, populated by every real pipeline run) |
| Credit | `/api/v1/metrics/credit` | POST | `app.credit.benchmark.run_phase1_report()` | Reads every application from `app.services.applications.store` (Postgres-backed) |
| Property Valuation | `/api/v1/metrics/property` | POST | `app.property_valuation.benchmark.run_coverage_report()` | Reads every application from the same `store` |

Three of these are POST even though they only read data, because "read" undersells what they do — Document Ingestion's benchmark *runs the real agent* (real PDF generation, real OCR/parsing, several seconds of work), and Credit/Property both do a live multi-query sweep over the application store. GET is reserved for `/evaluation/runtime`, which really is a cheap read of an in-memory list.

Each endpoint is a thin FastAPI handler that does one `from app.X.benchmark import run_Y; return run_Y()` — all the actual logic lives in the `benchmark.py` module next to that agent's `metrics.py`, so the metrics math and the "where does the real data come from" wiring stay separate and independently testable.

### 2.3 Document Ingestion Agent — `app/document_ingestion/benchmark.py`

`run_bundled_demo_benchmark()`:
1. Generates 6 demo document bundles in memory (`tests/mock_data/generate_docs.py`): clean-prime, name-discrepancy, salary-discrepancy, missing-docs, correctable-PAN-error, image-upload — 35 real PDF/image files total, each with hand-written, known ground truth (`BUNDLE_LABELS`, `SALARY_RECONCILES` dicts in the same file).
2. Runs the **real** `DocumentIngestionAgent.process_document_bundle()` on each bundle — actual OCR, actual field extraction, actual contradiction detection.
3. Feeds the real outputs plus the hand-written ground truth into the pure metric functions in `app/document_ingestion/metrics.py`: `compute_classification_metrics`, `compute_cost_weighted_error`, `compute_brier_score`, `compute_ece`, `compute_gate_passing_error_rate`, `compute_reconciliation_metrics`, `compute_operational_metrics`.
4. Also runs a dedicated field-level check on the clean-prime bundle (`compute_exact_match`, `compute_token_f1`, `compute_numeric_accuracy`) against its fully-known field values (PAN, borrower name, gross salary, bank AMB).

A thin CLI wrapper, `backend/scripts/document_ingestion_metrics_report.py`, calls the same `run_bundled_demo_benchmark()` and pretty-prints it — it exists so this benchmark can be run from a terminal without starting the server, and is what originally replaced the fabricated 40-case benchmark this document's history refers to.

**Why this one is "runnable" in the fullest sense**: it needs no application history and no database — the bundles and their ground truth are generated fresh on every call, so the result is always a measurement of the current code against a fixed, known-good answer key.

### 2.4 Decision Agent — audit-log wiring

`GET /evaluation/runtime` reads `app.services.audit.audit_store`, an in-memory `AuditStore` (`app/services/audit.py`). Until this session, nothing ever called `create_audit_record()` — the endpoint existed and worked, but the store it read from was always empty. The fix was in `app/services/applications.py::run_application()`: right after building the application view, it now does

```python
decision_result = DecisionResult.model_validate(result.get("decision") or {})
create_audit_record(
    application_id=app_id,
    validation=result.get("validation_result"),
    contradictions=result.get("contradictions"),
    risk_assessment=result.get("risk_assessment"),
    confidence_assessment=result.get("confidence_assessment"),
    crew_output=result.get("decision_crew_output"),
    final_decision=decision_result,
    errors=[...],
)
```

so every real run through `/api/v1/underwriting/run` (upload, demo scenario, or rerun) now appends a record. `runtime_metrics_from_decisions()` then aggregates whatever is in that list into `n_decisions`, `decision_distribution`, `suspend_rate`, `auto_decision_rate`, `mean_confidence`, `below_threshold_rate`, `gate_trigger_counts`.

**Known, documented limitation** (stated directly in the card's description): `audit_store` is in-memory and resets on server restart, while the Applications list is Postgres-backed and persists. This means the card can legitimately read "0 decisions audited" right after a restart even though dozens of applications exist — that's not a bug, just a mismatch between two different stores, and the card says so.

### 2.5 Credit Agent — `app/credit/benchmark.py`

`run_phase1_report()` implements only **Phase 1** of `CREDIT_METRICS.md` — the half explicitly documented as needing "only applications already stored," as opposed to Phase 2 (needs two saved batches, for drift/PSI) or Phase 3 (needs closed-loan outcomes, which this system has nowhere to store).

```python
def _build_records() -> list[dict]:
    for view in store.list():                      # every stored application
        records.append({
            "application_id": view["id"],
            "credit_analysis": agents.get("credit") or {},
            "decision": view.get("decision") or ...,
            "gender": _gender_for(...),             # from the Aadhaar doc's parsed fields only
            "field_overrides": _field_overrides_for(...),
            "outcome_bad": None,                     # never captured - always None
        })
    return records
```

`gender` is pulled specifically from the Aadhaar document's `parsed_fields.fields.gender` (never from the application view itself — `CREDIT_METRICS.md` is explicit that gender must never be an input to `credit_node`, only an audit attribute read out-of-band for the adverse-impact check). `field_overrides` is built per document that has parsed fields, `{doc_id: overrides_or_empty_dict}`, matching the shape `app.credit.metrics.normalize_record` expects (and matching what the original psql-export-based CLI, `scripts/credit_metrics_report.py`, produces from the live database — this module is the in-process equivalent of that export, so both paths feed the exact same `phase1_report()` function).

The records are passed to `app.credit.metrics.phase1_report()`, which returns: `bureau_source_mix`, `flag_trigger_rates`, `decision_distribution`, `confidence_distribution`, `agreement_matrix` (Credit Agent's call vs. the Decision Agent's), `upstream_data_quality_rate`, `adverse_impact_ratio`.

If no applications are stored, `run_phase1_report()` short-circuits to `{"available": false, "reason": "..."}` rather than running `phase1_report()` on an empty list.

### 2.6 Property Valuation Agent — `app/property_valuation/benchmark.py`

`run_coverage_report()` implements only **Coverage Rate** from `PROPERTY_VALUATION_METRICS.md` — the one metric in that document needing no ground truth. PPE10/PPE20/MdAPE all need each property's actual closed-sale transaction price, which this system does not store anywhere (same category of gap as Credit's `outcome_bad`), so they are not computed here; FSD is not implemented at all (see §2.7).

```python
def _build_records() -> list[dict]:
    for view in store.list():
        prop = (view.get("agents") or {}).get("property") or {}
        records.append({
            "application_id": view.get("id"),
            "estimated_value": prop.get("estimated_value"),
            "value_source": <the "source" on the estimated_value evidence entry>,
        })
```

`value_source` is read off the `evidence` list that `property_valuation_node` already attaches to every run (`{"agent": "property", "field": "estimated_value", "value": ..., "source": value_source}`), so coverage can be broken down by which of the three valuation sources actually produced the number: `avnester` (live listings), `scraped_db` (the scraped comparables Postgres table), `local_db` (locality/city median fallback), or absent entirely (no source produced a usable valuation).

`app.property_valuation.metrics.coverage_rate(records)` computes `total_applications`, `valuations_produced`, `coverage_rate_pct`, `by_source`, `no_valuation_count`. The endpoint also always attaches `accuracy: valuation_accuracy_report(None)`, which — since no transaction-price pairs are ever passed in — always returns `{"available": false, "reason": "..."}`, so the frontend can render that explanation directly from the same response instead of needing a second call.

### 2.7 Why FSD (Forecast Standard Deviation) was never implemented

`PROPERTY_VALUATION_METRICS.md` is explicit that FSD must reflect the valuation model's *own* uncertainty methodology and must not be approximated as `stdev()` of raw historical errors unless that is literally how the model was designed. This agent's valuation is a deterministic comparable-median calculation (AVnester → scraped DB → local median fallback, in that order — see `property_valuation_node`), not a calibrated probabilistic model that outputs its own confidence interval. There is no honest FSD number to compute today; reporting one anyway would misrepresent post-hoc error spread as the model's self-assessed confidence. `app.property_valuation.metrics` has no `fsd` function, and none is wired into the benchmark — this is a deliberate omission, not an oversight.

### 2.8 Compliance Agent

No `app/compliance/benchmark.py`, no `app/compliance/metrics.py`, no methodology doc. The overview entry is simply `{"status": "unavailable", "description": "No evaluation framework exists yet for this agent.", "endpoint": None, "method": None}`. This was confirmed by searching every branch in the repository's git history (including unmerged ones) for any compliance-metrics code — none exists anywhere.

## 3. Frontend architecture

All of it lives in two files: `frontend/lib/underwriting-service.ts` (types + API calls) and `frontend/components/views.tsx` (the page and its sub-components). Routing is wired in `frontend/components/underwriting-app.tsx`.

### 3.1 Types (`underwriting-service.ts`)

- `AgentMetricsStatus` — mirrors the backend's `AGENT_METRICS_STATUS` entry shape.
- `DocumentIngestionMetricsReport`, `DecisionRuntimeMetrics`, `CreditPhase1Report`, `PropertyCoverageReport` — one type per agent's report shape, matching its endpoint's JSON exactly (nested objects typed out field-by-field rather than left as `any`, so the panel components get real autocomplete/type-checking).

### 3.2 Service calls (`underwritingService` object)

```typescript
getAgentMetricsOverview: () => request<AgentMetricsStatus[]>('/api/v1/metrics/overview'),
runDocumentIngestionMetrics: () => request<DocumentIngestionMetricsReport>('/api/v1/metrics/document-ingestion', { method: 'POST' }),
getDecisionRuntimeMetrics: () => request<DecisionRuntimeMetrics>('/evaluation/runtime'),
runCreditMetrics: () => request<CreditPhase1Report>('/api/v1/metrics/credit', { method: 'POST' }),
runPropertyMetrics: () => request<PropertyCoverageReport>('/api/v1/metrics/property', { method: 'POST' }),
```

`/evaluation/runtime` lives outside `/api/v1/*`, so `frontend/next.config.mjs` needed a second rewrite rule (`/evaluation/:path*` → the backend) added specifically to make this call reachable through the Next.js dev server proxy; without it, this one request would 404 while every other metrics call worked.

### 3.3 Components (`views.tsx`)

```
AgentMetrics                     — the page: fetches the overview, renders one AgentMetricCard per agent
└── AgentMetricCard               — one card: icon, status pill, description, "Run benchmark" button, result panel
    ├── DocumentIngestionMetricsPanel
    ├── DecisionMetricsPanel
    ├── CreditMetricsPanel
    └── PropertyMetricsPanel
```

`AgentMetricCard` holds one piece of state per possible report type (`docReport`, `decisionReport`, `creditReport`, `propertyReport` — only one is ever populated per card, since each card only ever calls its own agent's endpoint) plus `loading`/`error`. Its `run()` function is a single `switch`-like if/else on `status.agent` that calls the matching `underwritingService` method and stores the result; nothing is cached across cards or across page visits — every "Run benchmark" click is a fresh network call.

Each panel component handles its own agent's `available: false` case by rendering an empty-state block with the backend's `reason` string verbatim, rather than the card silently showing nothing or a misleading zero. For example, `CreditMetricsPanel` and `PropertyMetricsPanel` both start with:

```tsx
if (!report.available) {
  return <div className="panel empty-state">...<span>{report.reason}</span></div>
}
```

`CreditMetricsPanel` additionally renders a standalone warning banner when `bureau_source_mix.unverified_share_pct > 0` ("Read the bureau-source mix first") — surfacing `CREDIT_METRICS.md`'s own top-of-document warning directly in the UI, since most applications in this system use demo/simulated bureau data rather than a real bureau pull, and every other Credit number should be read with that in mind.

`PropertyMetricsPanel` always renders both the Coverage Rate stat cards (real numbers) *and* a "PPE10 / PPE20 / MdAPE not available" block pulled from `report.accuracy.reason` — both appear on the same screen, deliberately, so the gap between "what's measured" and "what isn't yet" is visible in one place rather than requiring the viewer to infer it from an incomplete card.

### 3.4 Routing

`underwriting-app.tsx`'s `View` union includes `'metrics'`; the sidebar's "Agent Metrics" nav item (`Activity` icon from `lucide-react`) sets that view, and `UnderwritingApp` renders `<AgentMetrics setView={setView} />` when active. No application needs to be selected to view this page — it's portfolio-wide, not per-application, unlike Agent Reports.

## 4. End-to-end data flow (concrete example: Credit Agent)

1. User opens **Agent Metrics**, page calls `GET /api/v1/metrics/overview`, renders a Credit Agent card marked `Runnable`.
2. User clicks **Run benchmark**. Frontend calls `POST /api/v1/metrics/credit`.
3. `credit_metrics()` in `main.py` imports and calls `run_phase1_report()`.
4. That function calls `store.list()` — every application row Postgres (or the in-memory fallback store) currently has, each already containing `agents.credit` from whenever that application was originally run through the full pipeline.
5. For each application, it looks up the Aadhaar document's parsed `gender` field and the saved field-overrides for every reviewable document — two more store queries per application.
6. The assembled records are handed to the pure, already-unit-tested `phase1_report()` function, which does no I/O at all.
7. The JSON result flows back through FastAPI → fetch → `CreditMetricsPanel`, which renders stat cards, a decision-distribution breakdown, red-flag trigger rates, and (conditionally) a severe-conflicts table and bureau-mix warning banner.

No step in this chain touches a cache, a precomputed value, or test/demo-only data — every number reflects whatever is actually in the database at the moment the button was clicked.

## 5. Tests

Each agent's `metrics.py` has a dedicated pure-function test file, independent of the HTTP layer and independent of each other:

- `backend/tests/test_document_ingestion_metrics.py`
- `backend/tests/test_credit_metrics_module.py` / `test_credit_correctness_metrics.py`
- `backend/tests/test_property_valuation_metrics.py` — every example reproduces a worked example from the source `Automated Valuation Model (AVM) — Evaluation Metrics.pdf` exactly, so the module is checked against the document, not just against itself.

None of these tests call a live external service (AVnester calls are mocked where relevant) or depend on network/database state — they test the math in isolation. The `benchmark.py` wiring layers (which do touch the store) are exercised indirectly through the full-pipeline tests in `test_hitl_review.py` and by direct manual verification against the running server, rather than their own dedicated unit tests, since they're thin glue with little logic of their own.

## 6. Known limitations, stated plainly

- **Decision Agent's audit log is in-memory.** Restarting the backend silently zeroes `n_decisions` even though the Applications list is unaffected. This is called out in the card's own description text, not hidden.
- **Credit Agent Phase 1 numbers are dominated by demo/simulated data** in any environment that hasn't wired in a real credit bureau — the card's own banner says this.
- **Property Valuation's Coverage Rate can look low** not because the agent is broken, but because AVnester (the primary source) doesn't cover every locality, and the scraped-DB/local-median fallbacks only have data where they've been seeded.
- **PPE10/PPE20/MdAPE (property) and Phase 3 AUC/KS/bad-rate (credit) are permanently unavailable** until this system starts persisting real outcomes (closed-sale price; closed-loan good/bad) — a schema change neither agent's current data model supports. Both methodology docs describe exactly what would need to be added.
- **Compliance Agent has no metrics implementation at all.**
