# Compliance Agent

The Compliance Agent sits alongside Credit Analysis and Property Valuation in the Mortgage Underwriting pipeline. It runs six categories of regulatory checks for Indian housing finance — KYC/CDD, cross-document identity consistency, PMLA/AML, RBI Fair Practices, NHB priority-sector eligibility, and RERA registration — and produces a structured, evidence-backed `ComplianceAnalysisResult` for the Decision Agent.

**Core principle: deterministic rules decide; the LLM only explains.** Same principle the Credit and Decision agents follow — `rule_status` and `critical_flags` are always plain, auditable Python; the LLM is used only to narrate the already-final result, and can never add, remove, or soften a flag.

**This agent is the Decision Agent's first safety gate.** Per `README_decision.md`'s finalizer, "Critical compliance flag present?" is evaluated *before* contradictions, confidence, or risk score — a single critical flag here forces `SUSPEND` regardless of how strong the rest of the application is.

---

## Table of Contents

1. [Pipeline](#pipeline)
2. [Module Layout](#module-layout)
3. [Input Contract](#input-contract)
4. [Output Contract](#output-contract)
5. [KYC / CDD](#kyc--cdd)
6. [Identity Consistency](#identity-consistency)
7. [PMLA / AML](#pmla--aml)
8. [RBI Fair Practices](#rbi-fair-practices)
9. [NHB Priority-Sector](#nhb-priority-sector)
10. [RERA Registration](#rera-registration)
11. [Confidence](#confidence)
12. [LLM Reasoning](#llm-reasoning)
13. [Configuration](#configuration)
14. [Dependencies](#dependencies)
15. [What's Stubbed / Assumed](#whats-stubbed--assumed)
16. [Tests](#tests)

---

## Pipeline

`compliance_node` (`backend/app/graph/nodes/compliance.py`) runs as a single LangGraph node, mirroring how `credit_node` and `decision_node` orchestrate their agents as one function calling into several pure modules:

```
1. Read borrower_profile, document_analysis, property_analysis from state
2. run_all_checks(...)         -> six deterministic checks, each pure (dict -> dict/str, flags)
3. compute_confidence(...)     -> this assessment's own reliability score
4. run_compliance_reasoning(...) -> LLM explains steps 2-3, never changes them
5. Assemble ComplianceAnalysisResult and write state["compliance_analysis"]
```

Unlike `credit_node`, this node does **not** short-circuit on missing upstream data — an empty/missing `document_analysis` flows through the normal rules engine and naturally produces a `KYC_INCOMPLETE` critical flag, which is the correct outcome ("incomplete KYC always results in Suspend, never Approve") rather than a special-cased error path.

Integration into `backend/app/graph/workflow.py`'s `StateGraph` is left for whoever wires the full ingestion → credit → property → compliance → decision chain together.

---

## Module Layout

```
backend/
├── config/
│   └── compliance_config.yaml          # Required docs, thresholds, confidence weights
├── app/
│   ├── agents/
│   │   └── compliance/
│   │       └── crew.py                 # Single CrewAI agent: explains, never decides
│   ├── compliance/
│   │   ├── config.py                   # YAML loader + in-code fallback defaults
│   │   ├── flags.py                    # Internal RuleFlag dataclass (not on the shared model)
│   │   ├── kyc_checks.py               # KYC / CDD completeness
│   │   ├── identity_consistency.py     # Cross-document name/DOB/PAN matching (rapidfuzz)
│   │   ├── pmla_aml.py                 # Source-of-funds / identity verification logging
│   │   ├── rbi_fair_practices.py       # Protected-attribute guard
│   │   ├── nhb_priority_sector.py      # Priority-sector loan ceiling classification
│   │   ├── rera_check.py               # RERA registration for under-construction property
│   │   ├── rules_engine.py             # Aggregates all six checks
│   │   └── scoring.py                  # confidence calculation
│   ├── graph/
│   │   └── nodes/
│   │       └── compliance.py           # compliance_node entry point
│   └── models/
│       └── decision.py                 # ComplianceAnalysisResult (shared file, not modified — already existed)
└── tests/
    ├── test_compliance_kyc.py
    ├── test_compliance_identity.py
    ├── test_compliance_rbi.py
    ├── test_compliance_pmla.py
    ├── test_compliance_nhb.py
    ├── test_compliance_rera.py
    ├── test_compliance_scoring.py
    ├── test_compliance_crew.py         # Summary builder only, no real LLM call
    └── test_compliance_node.py         # Full node, LLM reasoning monkeypatched
```

---

## Input Contract

Reads three fields off `UnderwritingState`, populated by upstream agents:

```json
{
  "borrower_profile": {
    "loan_amount": 3500000,
    "property_city_tier": "metro"
  },
  "document_analysis": {
    "kyc": {
      "documents": [
        {"doc_type": "PAN", "present": true, "valid": true, "readable": true},
        {"doc_type": "AADHAAR", "present": true},
        {"doc_type": "ADDRESS_PROOF", "present": true}
      ],
      "pmla": {
        "source_of_funds_declared": true,
        "identity_verification_logged": true
      }
    },
    "borrower_identity": {
      "application_form_name": "Priya Sharma",
      "application_form_dob": "1994-03-12",
      "application_form_pan_number": "ABCDE1234F",
      "pan_card_name": "Priya Sharma",
      "pan_card_number": "ABCDE1234F",
      "aadhaar_name": "Priya Sharma",
      "aadhaar_dob": "1994-03-12",
      "salary_slip_name": "Priya Sharma",
      "bank_account_name": "Priya Sharma"
    }
  },
  "property_analysis": {
    "under_construction": false,
    "rera_status": "REGISTERED"
  }
}
```

> **Assumption flagged:** `document_analysis.kyc` / `.borrower_identity` and `property_analysis.rera_status` / `.under_construction` are inferred from `README_decision.md`'s Document/Property Analysis contracts — the real Document Ingestion and Property Valuation node code wasn't available while building this. Only `_extract_compliance_input` in `compliance.py` needs to change if those upstream shapes differ; every check function underneath is upstream-agnostic (plain dicts in, plain results out).

---

## Output Contract

Writes `state["compliance_analysis"]` as a `ComplianceAnalysisResult` dict (model already defined in `app/models/decision.py` — this branch does not modify it):

```json
{
  "kyc_cdd": {"status": "PASS", "missing_documents": []},
  "identity_consistency": "PASS",
  "pmla_source_of_funds": {
    "status": "PASS",
    "source_of_funds_declared": true,
    "identity_verification_logged": true
  },
  "rbi_fair_practices": {"status": "PASS", "protected_attributes_detected": []},
  "nhb": {"status": "PASS", "priority_sector_eligible": true, "details": "..."},
  "rera": {"status": "NOT_APPLICABLE", "registered": null},
  "rule_status": {
    "kyc_cdd": "PASS",
    "identity_consistency": "PASS",
    "pmla_source_of_funds": "PASS",
    "rbi_fair_practices": "PASS",
    "nhb": "PASS",
    "rera": "NOT_APPLICABLE"
  },
  "critical_flags": [],
  "confidence": 0.90,
  "evidence": [...]
}
```

`kyc_cdd`, `pmla_source_of_funds`, `rbi_fair_practices`, `nhb`, and `rera` are dicts (each with at least a `status`); `identity_consistency` is a plain status string — this matches the field types already defined on `ComplianceAnalysisResult`, not a convention introduced here. `critical_flags` is a flat `list[str]` — only CRITICAL-severity issues appear here; everything else (warnings, informational) lives in `rule_status` and the individual check dicts. The LLM's plain-language explanation isn't a field on the shared model (unlike Credit's `reasoning`), so it's carried as an `evidence` entry with `field="reasoning"` instead — it survives into the report/audit trail without changing the shared model's shape.

---

## KYC / CDD

Checks that PAN, Aadhaar, and Address Proof are all present, valid, and readable. Any one missing/invalid produces a `KYC_INCOMPLETE` flag — **CRITICAL**, always forces `SUSPEND`. This is deliberate: an incomplete KYC file must never result in an automated Approve.

## Identity Consistency

Cross-checks the applicant's name/DOB/PAN across the application form, PAN card, Aadhaar, salary slip, and bank account, using `rapidfuzz` (`token_sort_ratio`, threshold 90) so formatting differences (reordered names, middle names) don't produce false mismatches.

| Mismatch | Flag | Severity |
|---|---|---|
| Name differs across documents | `IDENTITY_MISMATCH_NAME` | MEDIUM (warning) |
| DOB differs (form vs Aadhaar) | `IDENTITY_MISMATCH_DOB` | HIGH (warning) |
| PAN number differs (form vs card) | `IDENTITY_MISMATCH_PAN` | **CRITICAL** → SUSPEND |

## PMLA / AML

| Missing | Flag | Severity |
|---|---|---|
| Source-of-funds declaration | `PMLA_SOURCE_OF_FUNDS_MISSING` | **CRITICAL** → SUSPEND |
| Identity verification log | `PMLA_IDENTITY_LOG_MISSING` | MEDIUM (warning) |

## RBI Fair Practices

Defensive guard: scans every field passed through decision logic for protected attributes (`religion`, `caste`, `gender`, `region` — configurable). Any hit → `PROTECTED_ATTRIBUTE_USED`, **CRITICAL** → SUSPEND. Aggregate fairness monitoring across many decisions is a separate batch job, out of scope for this real-time check.

## NHB Priority-Sector

Classifies the loan against metro/non-metro priority-sector ceilings (Phase-1 placeholder figures — see [What's Stubbed](#whats-stubbed--assumed)). Informational only: `NHB_PRIORITY_SECTOR_MISCLASSIFIED` is LOW severity and never contributes to `critical_flags` or a SUSPEND.

## RERA Registration

For under-construction properties only: if `property_analysis.rera_status != "REGISTERED"`, produces `RERA_NOT_REGISTERED`, **CRITICAL** → SUSPEND, since the Property Valuation Agent's output can't be trusted for an unregistered project. Not applicable to already-built properties.

---

## Confidence

How reliable *this specific assessment* is (evidence quality), not a judgment about the applicant — same meaning as `confidence` elsewhere in this system (`app.decision.confidence`, `app.credit.scoring`).

```
confidence = 0.90
           - 0.15 per CRITICAL flag
           - 0.05 per MEDIUM/HIGH ("warning") flag
           floor 0.30, ceiling 1.0
```

LOW-severity flags (e.g. the NHB informational flag) don't dock confidence.

---

## LLM Reasoning

`app.agents.compliance.crew.run_compliance_reasoning` runs a single CrewAI `Agent`/`Task` ("Compliance Reviewer") that explains the already-final rule results in 2-4 sentences. On any failure (CrewAI not installed, LLM outage, parse error) it falls back to a deterministic template string rather than raising — the pipeline never blocks on this step.

`_build_compliance_summary` (the prompt's structured input) and `_template_reasoning` (the fallback) are pure functions, unit-tested directly in `test_compliance_crew.py` without invoking a real LLM.

---

## Configuration

**File:** `backend/config/compliance_config.yaml`

```yaml
required_kyc_documents: [PAN, AADHAAR, ADDRESS_PROOF]
fuzzy_match:
  name_match_threshold: 90
pmla_aml:
  require_source_of_funds_declaration: true
  require_identity_verification_log: true
nhb_priority_sector:
  metro_ceiling: 3500000
  non_metro_ceiling: 2500000
rera:
  required_for_under_construction: true
protected_attributes: [religion, caste, gender, region]
confidence:
  base: 0.90
  critical_flag_penalty: 0.15
  warning_flag_penalty: 0.05
  floor: 0.30
```

If the file is missing, `app.compliance.config.get_compliance_config` falls back to identical in-code defaults, so tests and a fresh checkout work without it.

---

## Dependencies

One new third-party dependency beyond what the repo already uses:

| Package | Why |
|---|---|
| [`rapidfuzz`](https://pypi.org/project/rapidfuzz/) | Fuzzy name matching in `identity_consistency.py`, so formatting differences across documents don't produce false mismatches |

Everything else (`pydantic`, `pyyaml`, `crewai`) is already a project dependency via the Credit/Decision agents. Install with:

```bash
pip install rapidfuzz
```

and add `rapidfuzz` to `backend/pyproject.toml`'s `dependencies` list so it's picked up automatically on a fresh install.

---

## What's Stubbed / Assumed

- **NHB priority-sector ceilings** (`metro_ceiling`, `non_metro_ceiling`) — Phase-1 placeholder figures. `# TODO: replace with the exact NHB circular values once sourced.`
- **Upstream field names** (`document_analysis.kyc`, `.borrower_identity`, `property_analysis.rera_status`) — inferred from `README_decision.md`'s contracts, not confirmed against real Document Ingestion / Property Valuation node code. See the note in [Input Contract](#input-contract).
- **LLM instantiation pattern in `crew.py`** — assumes CrewAI's `Agent(llm="<provider>/<model>")` string form built from `app.services.llm.get_llm_config()`. Not confirmed against `app.agents.credit.crew` or `app.agents.decision.crew`'s actual implementation — `# TODO: align with the real primary→fallback retry pattern once visible.`
- **LangGraph wiring** — `compliance_node` is a standalone function; it isn't yet registered in `app/graph/workflow.py`'s `StateGraph`. Left for whoever wires the full pipeline together, matching how the Credit and Decision branches also added their node functions without chaining them.

Everything else — all six checks, the confidence formula, and the rules engine — is real, deterministic Python.

---

## Tests

```bash
cd backend
pytest tests/test_compliance_*.py -v
```

| File | Covers |
|---|---|
| `test_compliance_kyc.py` | All-present pass, missing/invalid document detection |
| `test_compliance_identity.py` | Name/DOB/PAN matching, fuzzy tolerance, missing-data handling |
| `test_compliance_rbi.py` | Protected-attribute detection, case-insensitivity, multiple hits |
| `test_compliance_pmla.py` | Source-of-funds and identity-log requirements |
| `test_compliance_nhb.py` | Metro/non-metro ceilings, missing-data handling |
| `test_compliance_rera.py` | Under-construction + registered/unregistered, not-applicable case |
| `test_compliance_scoring.py` | Confidence formula bounds, penalty weighting by severity |
| `test_compliance_crew.py` | Summary builder content, template fallback (no real LLM call) |
| `test_compliance_node.py` | Full node — clean pass, KYC failure, RERA failure, missing upstream data, output validates against `ComplianceAnalysisResult` |

41 tests total, all passing against the real `app.models.decision.ComplianceAnalysisResult`.

---

## Disclaimer

This is a decision-support/pre-screening output, consistent with the rest of this system (see `README_decision.md`). Prototype thresholds and weights here (NHB ceilings, fuzzy-match threshold, confidence penalties) are engineering choices, not official RBI/NHB/lender regulatory requirements.
