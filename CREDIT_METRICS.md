# Credit Agent evaluation metrics

Measurement only. Nothing here changes a credit rule, threshold, weight, score formula or `backend/config/credit_config.yaml`, and nothing in `app.credit.metrics` is imported by the agent.

- Code: `backend/app/credit/metrics.py` (standard library only, pure functions)
- Report CLI: `backend/scripts/credit_metrics_report.py` (reads an exported file, never touches the DB)
- Tests: `backend/tests/test_credit_metrics_module.py` (metric maths), `backend/tests/test_credit_correctness_metrics.py` (real `credit_node`)

**Status key** - **Now**: needs only applications already stored. **Next**: needs two batches (a stored baseline). **Later**: needs closed-loan outcomes, which this system does not record yet.

> **Read the bureau-source mix first.** Until a real bureau is wired in, most applications use simulated or declared data (`raw_data.bureau_source`). Simulated scores are derived from the application id, not the borrower, so every other number measures the stub rather than real credit risk. The report puts this table at the top for that reason.

## Running it

```bash
cd backend
python scripts/credit_metrics_report.py --input applications.jsonl                  # Phase 1 (+ outcomes if labelled)
python scripts/credit_metrics_report.py --input batch2.jsonl --baseline baseline.json   # adds PSI
python scripts/credit_metrics_report.py --input batch1.jsonl --save-baseline baseline.json
```

Export SQL is in the script's docstring. In Python:

```python
from app.credit import metrics as m
records = m.normalize_records(rows)      # rows with the full application in applications.view
m.phase1_report(records)
```

## Phase 1 - no outcomes needed (Now)

| Metric | Formula / definition | Target | Function |
|---|---|---|---|
| Bureau source mix | count and % of `bureau`, `applicant_declared`, `simulated`, `demo_fixture`, `unknown`, read from `credit_analysis.raw_data.bureau_source` | 0% simulated in production (`meets_production_target`) | `bureau_source_mix` |
| Red-flag trigger rates | % of applications carrying each flag (settled, written-off, DPD>90, loan stacking, income-to-loan). Flags are free-text strings, classified by substring. Zero-rate flags still listed | no fixed target; a flag at exactly 0% on a large batch means the data source cannot trigger it (the simulated stub never produces settled/written-off/DPD) | `flag_trigger_rates` |
| Decision distribution | APPROVE / CONDITIONAL / REJECT counts and % of `preliminary_decision` | watch for sudden swings between batches | `decision_distribution` |
| Confidence distribution | 0.05-wide histogram; % at the 0.30 floor; per-application check `confidence = 0.90 - 0.30 (New-to-Credit) - 0.05 x flag_count`, floored at 0.30, capped at 1.0 (constants read from `credit_config.yaml::confidence`) | alert if >20% at the floor; 0 formula mismatches | `confidence_distribution` |
| Credit vs Decision agreement | 3x3 matrix with APPROVE->APPROVE, CONDITIONAL->SUSPEND, REJECT->DENY; agreement rate; every off-diagonal case; severe conflicts = Credit APPROVE vs Decision DENY, Credit REJECT vs Decision APPROVE | 0 severe conflicts; agreement is informational (the Decision Agent legitimately uses more inputs) | `agreement_matrix` |
| Upstream data-quality rate | of applications with review data, % where a reviewer overrode `monthly_income`, `existing_debt`, or an upstream income/obligation field (`gross_salary`, `net_salary`, `average_monthly_salary_credit`, `total_monthly_obligations`) | lower is better; a rising rate points at extraction quality, not the credit rules | `upstream_data_quality_rate` |
| Adverse impact ratio | favourable = APPROVE (also APPROVE+CONDITIONAL); AIR = lowest group rate / highest group rate; flagged when AIR < 0.80. Fewer than 2 groups or a highest rate of 0 returns `air: null` with a status, never an error | AIR >= 0.80 | `adverse_impact_ratio` |

Notes on the less obvious ones:

- **Adverse impact ratio** is an audit run *outside* the decision path. Gender is never an input to `credit_node`. Below 0.80 is a trigger for investigation, not proof of discrimination, and groups under 30 applications are flagged as statistically unreliable. **The four-fifths rule is a US screening benchmark (EEOC), not an Indian regulation.** Gender is not stored in the application `view`; it is only in the Aadhaar document's parsed fields, so the export SQL joins it in.
- **Upstream data-quality**: `credit_node` reads `monthly_income` and `existing_debt` from the application form (`borrower_profile`), not from the extracted documents. The salary-slip and bank-statement fields are therefore an indirect signal (extraction quality of the documents a reviewer cross-checks the form against), and `monthly_income` / `existing_debt` only count if they appear as override keys. "Reviewed" currently means "has parsed documents" (see the proposal below for a real review flag).
- **Credit vs Decision agreement** compares the Credit Agent's own call with the final recommendation; disagreement is expected sometimes. The severe-conflict list is the part to read.

## Phase 2 - drift (Next)

| Metric | Formula | Target | Function |
|---|---|---|---|
| PSI on `risk_score` | per band: `(cur% - base%) x ln(cur% / base%)`, summed; empty bands use epsilon 1e-4. Band edges come from `quantile_edges(baseline, n_bins)` (descending cut-offs; 10 bands in the CLI) | < 0.10 stable; 0.10-0.25 moderate shift (investigate); > 0.25 significant shift | `psi`, `psi_from_shares`, `quantile_edges` |

Needs two batches: save one with `--save-baseline`, compare a later one with `--baseline`. PSI says the score distribution moved, not why - a change in bureau-source mix (e.g. simulated -> real) will show up here as a large shift.

## Phase 3 - needs closed-loan outcomes (Later)

Label convention: `outcome_bad` = 1 Bad, 0 Good; higher `risk_score` = better. `outcome_report(records)` returns `{"available": false, "reason": ...}` when no record is labelled and never fabricates numbers. Nothing in the current schema stores an outcome, so today this section always reports "not available".

| Metric | Formula | Target | Function |
|---|---|---|---|
| AUC | P(random Good scores above random Bad), ties count half (rank-based) | > 0.80 good, > 0.70 acceptable, else weak | `auc`, `auc_status` |
| Gini | `2 x (AUC - 0.5)` | - | `gini` |
| KS | max abs(cum%Good - cum%Bad) walking from the top score down. With `edges` it is evaluated per band | > 25% good, 20-25% acceptable, else weak | `ks_statistic`, `ks_status` |
| Bad rate by group | bad rate per `credit_band` (Excellent, Good, Fair, Poor, Very Poor) and `credit_risk_tier` (low, moderate, high); checks it rises monotonically in that order | monotonic | `bad_rate_by_group` |
| Confidence calibration | bucket by `confidence` (0.3-0.5-0.7-0.9-1.0); compare mean confidence with the share of definite calls (APPROVE = Good, REJECT = Bad) that were right; well calibrated when within 0.10 | within 0.10 | `confidence_calibration` |

Worked example from the metrics document (`risk_score, outcome`: 92G 88G 81G 74G 68B 61G 55B 47B 39B 28B): AUC = 0.96, Gini = 0.92, KS = 0.60 **with band edges [80, 65, 50]**. The exact per-score KS of that same data is 0.80, so always say which KS basis you report (`ks_basis` in the output).

Calibration caveat: in this system `confidence` means *evidence quality* (how complete the inputs were), not the probability that the call is right. Poor calibration is therefore a finding about the definition, not necessarily a defect. CONDITIONAL calls are referrals and are excluded from the correctness check.

## Correctness checks on the agent itself (Now)

`tests/test_credit_correctness_metrics.py` runs the real `credit_node` with pinned bureau data:

- **Determinism**: 20 runs on one state give an identical `CreditAnalysisResult.model_dump()` (timestamp-like keys stripped).
- **Monotonicity** (black box): `risk_score` never falls as `cibil_score` rises 300-900; never rises as `existing_debt` (FOIR) rises; falls strictly with each added severe red flag (settled, written-off, DPD>90).
- **Branch coverage** of `generate_preliminary_decision`: one test per ordered branch. The function has 8 return points (3 REJECT, 4 CONDITIONAL, 1 default APPROVE), not 7.

Measure it with `pytest tests/test_credit_*.py --cov=app.credit --cov-branch --cov-report=term-missing` (needs `pytest-cov`, which is not in `pyproject.toml`; `coverage run --branch -m pytest ...` works with the already-installed `coverage`).

## Correction to the source document: what one severe red flag costs

The source document says one severe red flag lowers the score by 30 points. In the code it lowers the **red-flag component** by 30 (`credit_config.yaml::risk_score.red_flag_penalty.severe`), and that component carries weight 0.20 in `risk_score` (`weights.red_flags`). The total therefore drops by `30 x 0.20 = 6` points, which `test_one_severe_flag_costs_about_six_total_points_not_thirty` verifies against the real node. A mild flag costs `12 x 0.20 = 2.4` points. (A severe flag matters far more through the decision rules: two severe flags force a REJECT, one forces at least CONDITIONAL.)

## What to start capturing (PROPOSAL - no schema change made)

Phase 3 and a trustworthy "reviewed" rate need data the schema does not hold. Proposed, for a later migration:

1. **Outcome label per `application_id`**: `outcome_bad` (nullable smallint, 1/0), `outcome_observed_at`, and `observation_window_months` (e.g. 12 - "bad" = 90+ DPD within the window). Only applications that were actually disbursed can have one, which also means the labelled set is biased towards approvals; document that when reporting AUC/KS.
2. **Baseline score snapshot for PSI**: a small table or JSON file of `risk_score` values (or the bin edges and shares) for the reference period, with the date range and bureau-source mix it covers, so PSI does not depend on someone remembering to run `--save-baseline`.
3. **Reviewed flag**: `documents.reviewed_at` (or `applications.reviewed`) so the data-quality denominator means "a human actually reviewed this" rather than "has parsed documents".
4. **Audit attributes** (gender and any others you want to monitor) stored in a separate audit table keyed by `application_id`, outside the decision path, instead of being dug out of `documents.parsed_fields`.

## Not implemented

- Nothing is computed from real outcomes: there are none to compute from.
- Per-document-type breakdown of overrides (only the combined rate and per-field counts).
- Statistical significance / confidence intervals on AIR beyond the small-group warning.
