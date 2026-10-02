# Credit bureau data: source tracking and interim measures

Branch: `feature/credit-bureau-source-tracking`

## Problem
Uploaded applications use `fetch_credit_report(application_id)`, which hashes the application ID into a score between 300 and 900. Nothing about the borrower goes into it, so the same documents can approve or suspend depending on the sequence number. Settled accounts, written-off accounts and DPD are always 0, so those red flags never trigger. Only the four demo scenarios (pinned bureau fixtures) were reliable.

## What a real bureau integration needs (not done)
1. A bureau agreement (CIBIL / Experian / Equifax / CRIF High Mark): credentials, contract, fees.
2. Applicant consent with an audit record.
3. PAN as the lookup key, fetched from the secure document store at call time and never placed on the graph state or logs.
4. A mapping from the provider response to the agent's fields.
5. Edge cases: no history, timeouts and outages, caching per PAN.

Items 1 and 3 need external credentials and agreements, so a real pull is **not** implemented. This branch implements the interim options and prepares the seam for the real integration.

## Changes
**Backend**
- `services/credit_bureau.py`
  - Every report carries a `source`: `bureau`, `applicant_declared`, `simulated` or `demo_fixture`.
  - The stub is tagged `simulated`, and its docstring now says plainly that it is not the borrower's credit.
  - `fetch_from_bureau()` is the single place for the real integration; it raises `BureauNotConfigured` and documents the PAN, consent, outage and caching requirements.
  - `map_bureau_response()` maps a provider payload to the agent's fields and treats a score of 0 or below as new-to-credit.
  - `declared_score_report()` and `validate_cibil_score()` handle a manually entered score (300-900).
  - `resolve_bureau_data()` picks the best source: real bureau, then declared score, then stub.
- `graph/nodes/credit.py`: uses `resolve_bureau_data`, and records `raw_data.bureau_source` and `bureau_source_label`. The CIBIL evidence source becomes `credit_bureau:<source>`. The credit rules and scoring are unchanged.
- `main.py`: `/api/v1/underwriting/run` accepts optional `declared_cibil_score` (400 if out of range) and `bureau_consent`.
- `services/applications.py`: demo fixtures are tagged `demo_fixture`. A consent record (`given`, `recorded_at`) is stored on the application view.

**Frontend** (`components/views.tsx`, `app/globals.css`)
- Optional "CIBIL score" field and a bureau-consent checkbox on the new-application form, with client-side range validation.
- The Credit report shows an amber notice when the data is not from a real bureau: "Simulated bureau data" or "Applicant-declared score".

**Docs**: `README_credit.md` updated.

## Tests
- Added `backend/tests/test_credit_bureau.py` (stub tagging and determinism, fallback when no provider is configured, declared-score validation, response mapping and new-to-credit, source reported by the node).
- `pytest tests/test_credit_*.py`: **47 passed**.
- Not run: the rest of the suite fails to import in this environment (`rapidfuzz` and other dependencies missing), and the frontend was not type-checked or run (no `node_modules`). Both should be checked in CI or locally.

## Known limits
- A declared score is unverified. Only the score is known, so the DPD, settled and written-off checks run on neutral defaults.
- The consent flag is stored on the in-memory application view only. It is not yet used to gate anything, because no pull happens.
- With no score entered, uploads still use the simulated stub. They are now clearly labelled, but the approve/suspend outcome is still not trustworthy.
