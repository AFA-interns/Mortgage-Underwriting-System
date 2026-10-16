# DOCUMENT INGESTION AGENT
# Evaluation Metrics & Rationale

**Mortgage Underwriting System**  
*India-focused • Fully automated • No human review in the decision path*

> **Purpose:** Document what each Document Ingestion Agent metric measures, why it was selected, and how it supports safe, explainable underwriting evaluation when every case is resolved by the agent without human validation.

---

## 1. Evaluation Context

The Document Ingestion Agent is evaluated as a **fully automated hybrid system**. Its spatial extraction core performs multi-format document intake, layout text parsing, structured Pydantic schema extraction, field provenance tracking, deterministic validation, cross-document reconciliation, and finalization. The deterministic layer remains authoritative for all regulatory and financial rules. 

**No case is routed to a human reviewer**: every case ends in an automated outcome, and when the evidence is uncertain the agent takes the most conservative outcome, never `PROCEED`.

### Key Outputs Produced

| Output | Range / Type | Meaning |
| :--- | :--- | :--- |
| `document_type` | Enum (8 classes) | `PAN_CARD`, `AADHAAR`, `SALARY_SLIP`, `FORM_16`, `ITR`, `BANK_STMT`, `PROPERTY`, `UNKNOWN` |
| `field_extractions` | Pydantic Models | Structured borrower KYC, income, banking aggregates, and property specifications |
| `provenance` | Doc + Page + Snippet | Audit trail establishing the exact source evidence for every extracted value |
| `confidence` | 0–1 | Evidence reliability; 0.85 or above is the condition for `PROCEED` |
| `gate_triggered` | e.g. `missing_docs` | Safety gate that fired; selects the automated action |
| `automated_disposition` *(new)* | Enum (4 outcomes) | Outcome of the case, with no human step |

### Automated Outcomes Hierarchy

| Automated outcome | State | What happens |
| :--- | :---: | :--- |
| `PROCEED` | Terminal | All checks pass and confidence is 0.85 or above; data goes to the credit agent as extracted. |
| `PROCEED_CONSERVATIVE` | Terminal | The case continues on the lower, more cautious verified value; the discrepancy is attached so downstream agents see it. |
| `REQUEST_RESUBMISSION` | Pending | The agent sends the borrower an automatic request naming the missing, unreadable or conflicting document. The case is parked on a timer and re-enters the pipeline when files arrive. |
| `CLOSE_UNRESOLVED` | Terminal | The timeout expires, the maximum number of attempts is reached, or a hard conflict stays unresolved; the case is closed with the reasons recorded. |

- **Conservativeness order, most to least:**  
  $$\text{CLOSE\_UNRESOLVED} > \text{REQUEST\_RESUBMISSION} > \text{PROCEED\_CONSERVATIVE} > \text{PROCEED}$$  
  When several triggers fire on one case, the most conservative outcome wins. The same order is used to score false accepts and false rejects (section 7).
- **Termination and re-entry:** A pending case becomes `CLOSE_UNRESOLVED` when the resubmission timeout expires or the maximum number of attempts is reached; both are configuration values (section 7), so every case reaches a terminal outcome. When files arrive, the whole case is re-evaluated on the union of old and new documents, the new result supersedes the old one, and the audit trail is append-only.
- **Three metric families are required:** (1) correctness metrics against labeled ground truth, (2) calibration metrics for the confidence score, and (3) automation and safety metrics measured from the audit trail.

---

## 2. Dataset and Ground Truth

The shipped evaluation dataset contains **40 labeled synthetic cases** comprising over **160 individual files**. Labels are assigned independently from model predictions according to underwriting design intent, avoiding self-confirmation. The 25 edge cases that human review used to catch now each need an expected automated outcome.

| Case class | Cases | Rule for the expected automated outcome |
| :--- | :---: | :--- |
| **Clean Prime Salaried** | 15 | `PROCEED` |
| **Name Discrepancy** | 8 | Minor spelling variant: `PROCEED` after re-match. Genuine conflict: `REQUEST_RESUBMISSION`. |
| **Income Variance** | 7 | Within the variance limit: `PROCEED_CONSERVATIVE`. Beyond it: `REQUEST_RESUBMISSION`. |
| **Missing Docs** | 6 | `REQUEST_RESUBMISSION` |
| **Low-Quality Scans** | 4 | Recoverable by design: `PROCEED`. Otherwise: `REQUEST_RESUBMISSION`. |

- **Evaluation Principles:**
  - Each case receives exactly one expected outcome; the table gives the rule for choosing it. The benchmark scores the first-pass outcome, because no borrower reply is simulated.
  - Borderline cases are deliberately included, including minor spelling variants and variable payslip bonuses.
  - Safety-gate cases include `missing_mandatory_docs`, `salary_discrepancy`, `name_contradiction`, and `unmasked_aadhaar`.
  - The source does not say which name cases are spelling variants or which income cases exceed the variance limit, so those labels must be set per case. This is a one-time labeling task, not a review step in the live pipeline.
  - Add cases with forged or spliced documents; an unattended system has no one to notice them (section 10).
  - For production evaluation, supplement the synthetic labels with historical underwritten outcomes.

---

## 3. Classification Metrics

Classification metrics evaluate whether the predicted document type matches the labeled ground truth across all 8 classes. None of them depend on a reviewer.

| Metric | Definition | Why chosen |
| :--- | :--- | :--- |
| **Accuracy and balanced accuracy** | Correct predictions ÷ total cases; mean of per-class recall. | Package class mixes are unequal. Balanced accuracy stops a payslip-heavy mix hiding weak Form 16 or Property results. |
| **Per-class precision, recall, F1** | $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$; $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$; F1 is their harmonic mean. | Categories have unequal business consequences; `BANK_STMT` recall is the key safety guardrail. |
| **Macro and weighted averages** | Equal weight per class; weight by class support. | Macro gives a class-fair view; weighted reflects the real case mix. |
| **Confusion matrix** | Actual versus predicted type across all 8 classes. | Shows which error occurred: Bank read as Salary Slip is far worse than a scan sent to `UNKNOWN`. |
| **Cost-weighted error** | $\sum \text{cost}[\text{truth}][\text{prediction}] \div \text{total documents}$. | Errors are asymmetric; `BANK` read as `SALARY` has the highest prototype cost because it can book unverified credit. |

### Per-Class Precision & Recall Significance across all 8 Classes

| Class | Precision tells us | Recall tells us |
| :--- | :--- | :--- |
| `PAN_CARD` | How cleanly PANs are identified; limits false KYC. | Whether mandatory tax identity proof is captured. |
| `AADHAAR` | How reliably resident Aadhaar cards are identified. | Whether mandatory residential address proof is captured. |
| `SALARY_SLIP` | Limits false income proofs; avoids unstructured noise. | Whether all submitted monthly earnings periods are caught. |
| `FORM_16` | How justified annual tax certificate extractions are. | Whether statutory annual income proofs are caught. |
| `ITR` | How cleanly income tax returns are identified; limits false income proofs. | Whether filed-return income evidence is captured. |
| `BANK_STMT` | How accurately multi-page transaction ledgers are parsed. | Whether banking cash flows are caught; the most safety-critical recall. |
| `PROPERTY` | How cleanly collateral title deeds are identified. | Whether property collateral evidence avoids omission. |
| `UNKNOWN` | How often a file sent to `UNKNOWN` is truly unclassifiable; every wrong `UNKNOWN` triggers a borrower request. | Whether unclassifiable files are caught instead of forced into a wrong class. |

*Note: All 8 classes are covered explicitly.*

### Asymmetric Prototype Cost Matrix

$$\text{PAN} = \text{PAN\_CARD}, \quad \text{SALARY} = \text{SALARY\_SLIP}, \quad \text{BANK} = \text{BANK\_STMT}$$

| Truth \ Pred | `PAN` | `AADHAAR` | `SALARY` | `FORM_16` | `BANK` | `PROPERTY` | `UNKNOWN` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BANK`** | 8 | 8 | 10 | 6 | 0 | 8 | 2 |
| **`PAN`** | 0 | 4 | 8 | 6 | 8 | 8 | 2 |
| **`AADHAAR`** | 4 | 0 | 8 | 6 | 8 | 8 | 2 |
| **`SALARY`** | 8 | 8 | 0 | 3 | 10 | 8 | 2 |
| **`PROPERTY`** | 8 | 8 | 8 | 8 | 8 | 0 | 3 |

$$\text{Cost-weighted error} = \frac{\sum \text{cost}[\text{truth}][\text{prediction}]}{\text{total documents}}$$

- **Without a reviewer:** `UNKNOWN` used to be cheap because a human picked it up. It now triggers `REQUEST_RESUBMISSION`, so it stays cheap but costs the borrower a delay. Every other misclassification is uncaught, so the high costs describe real exposure. 
- *Note:* The matrix has rows for `BANK`, `PAN`, `AADHAAR`, `SALARY` and `PROPERTY` as true classes and no `ITR` column; add rows for `FORM_16`, `ITR` and `UNKNOWN` and an `ITR` column before treating cost-weighted error as complete.
- *Important: The cost matrix is configurable and represents an engineering evaluation choice, not an official regulatory cost schedule.*

---

## 4. Extraction & Validation Metrics

Extraction metrics evaluate whether granular fields and ledgers are extracted verbatim with full source provenance. A failed check now selects an automated action instead of waiting for a person.

| Metric | Definition | Why chosen | Automated action on failure |
| :--- | :--- | :--- | :--- |
| **Character and word error rate (CER, WER)** | Levenshtein distance to the reference ÷ reference length. | Separates OCR degradation from downstream parsing rules. | Feeds the low-confidence recovery passes. |
| **Exact match (EM)** | 1.0 if the normalized value equals the label, else 0.0. | Required for discrete identifiers such as PAN (`ABCPS1234F`) and IFSC (`HDFC0001234`). | A failed format check lowers confidence and triggers re-extraction. |
| **Token F1** | Token overlap between predicted and labeled value. | Tolerates variants such as "Limited" versus "Ltd" in employer names. | None; used for scoring only. |
| **Salary ledger reconciliation** | $\lvert\text{Gross} - (\text{Net} + \text{Deductions})\rvert \le \text{₹2.00}$ (rupees assumed). | Forged payslips often fail simple arithmetic; deterministic checks trap fraud before credit scoring. | Payslip excluded from income; `REQUEST_RESUBMISSION`. |
| **Provenance coverage** | Extracted fields with a valid (Doc, Page, Snippet) ÷ all extracted fields. | Keeps every value traceable for audit and for downstream agents. Target 100%. | A field without provenance is re-extracted or dropped, never passed on. |

---

## 5. Cross-Document Reconciliation Metrics

Reconciliation metrics evaluate whether the agent cross-examines data across independent documents. Contradiction recall is the most safety-critical metric and matters more now: a contradiction the agent misses goes straight to the credit agent with no one to stop it.

- **Name and income reconciliation accuracy:** Names are matched fuzzily across KYC, salary slips and bank statements; monthly net salary is reconciled against detected bank credits within $\pm 5\%$ tolerance.
- **Contradiction detection recall:** $\text{True contradictions detected} \div \text{total actual contradictions}$. Target benchmark is **$98.0\%$ or higher**.
- **Contradiction precision:** $\text{Real contradictions} \div \text{contradictions flagged}$. A false flag sends a resubmission request to a borrower with a clean file.
- **Contradiction handling accuracy (new):** $\text{Detected contradictions where automated action matches expected one} \div \text{all detected contradictions}$.

> **Small-Sample Note:** The benchmark has at most about 15 contradiction cases (8 name, 7 income variance). A perfect recall score on that few cases is still consistent with a true miss rate of up to about 20% (rule of three: $3 \div n$), so read 100% on this dataset as a floor, not proof.

---

## 6. Calibration Metrics

Calibration asks whether the confidence score means what it claims. A confidence of 0.90 should correspond to roughly a 90% probability of extraction correctness. Confidence of 0.85 or above is the condition for `PROCEED` and is now the only gate between an extraction error and the downstream agents.

- **What counts as correct:** The baseline appears to score correctness at the level of the case outcome. Define it explicitly: **a case is correct when its automated outcome equals the expected outcome and every field used downstream is within tolerance of its label.**
- **Brier score:** $\text{Mean squared error between confidence and correctness (1 correct, 0 incorrect)}$. Lower is better.
- **Expected Calibration Error (ECE):** $\sum (|B_m| \div N) \times |\text{acc}(B_m) - \text{conf}(B_m)|$ across 5 confidence bins. 0 is perfect calibration.
- **Gate-passing error rate (new):** Cases that are not correct and have confidence of 0.85 or above $\div$ all cases with confidence of 0.85 or above. This is the rate at which errors get through the gate unseen.

### Reliability Bins Diagnostic

| Confidence interval | Case count | Mean confidence | Actual accuracy | Calibration gap |
| :---: | :---: | :---: | :---: | :---: |
| 0.00 – 0.20 | 0 | 0.1000 | 0.0000 | 0.0000 |
| 0.20 – 0.40 | 0 | 0.3000 | 0.0000 | 0.0000 |
| 0.40 – 0.60 | 0 | 0.5000 | 0.0000 | 0.0000 |
| 0.60 – 0.80 | 12 | 0.6973 | 1.0000 | 0.3027 |
| 0.80 – 1.00 | 28 | 0.9142 | 1.0000 | 0.0858 |

- **Under-confident, not over-confident:** All 12 cases in the 0.60–0.80 bin fall below the 0.85 threshold and were correct; they now enter recovery or a resubmission request, which is avoidable friction.
- **ECE needs a re-run:** Weighting the two populated gaps by case count gives $0.3 \times 0.3027 + 0.7 \times 0.0858 \approx 0.151$, while the baseline reports 0.1489. At 0.151 the 0.150 target is just missed.
- **Gate failures are invisible:** Every populated bin has 100% accuracy, so the table cannot show whether a high-confidence extraction is ever wrong. Add wrongly extracted cases to the benchmark.
- **Proposed:** Tighten the ECE target to 0.050 and the gate-passing error rate to 0; recalibrate confidence (for example isotonic regression or Platt scaling) on a larger held-out set and choose the 0.85 threshold from that data.
- **Proposed:** Gate on the lowest confidence among decision-critical fields (name, PAN, net salary, bank credits, property value) as well as the overall score, so one weak field cannot be averaged away.

---

## 7. Automated Outcomes & Safety Metrics

These replace the straight-through-processing and HITL escalation metrics. Each safety gate maps to an automated action; no gate suspends a case for human review.

### Safety Gate Mapping

| Trigger | Automated action | Resulting outcome |
| :--- | :--- | :--- |
| `missing_mandatory_docs` | Send the borrower the list of missing document types and park the case on a timer; no agent can create a missing document. | `REQUEST_RESUBMISSION`, then `CLOSE_UNRESOLVED` on timeout or after the maximum attempts. |
| `salary_discrepancy` (net salary vs bank credits outside $\pm 5\%$) | Re-extract both figures once; if the gap remains, use the lower of payslip net salary and the average of detected salary credits over the same months. | `PROCEED_CONSERVATIVE`; above the salary variance limit, `REQUEST_RESUBMISSION`. |
| `name_contradiction` | Re-match using deterministic normalization only (initials, name order, transliteration); the similarity threshold is never lowered. | `PROCEED` if resolved; otherwise `REQUEST_RESUBMISSION`, then `CLOSE_UNRESOLVED`. |
| `unmasked_aadhaar` | Redact the first 8 digits before any extracted value, provenance snippet or log entry is written, so the full number is never stored. | `PROCEED`, if no other trigger fired. |
| `Ledger arithmetic mismatch` | Treat the payslip as unreliable, exclude it from income and request a replacement. | `REQUEST_RESUBMISSION`. |
| `Confidence below the threshold` (including low-quality scans) | At most two recovery passes: image preprocessing and re-extraction, then a second independent extractor compared field by field; confidence is recomputed after each. | `PROCEED` if confidence recovers to 0.85; otherwise `REQUEST_RESUBMISSION` for a rescan. |

### Configuration Parameters

| Parameter | Used for | Value |
| :--- | :--- | :--- |
| **Confidence threshold** | Condition for `PROCEED` | `0.85` (source) |
| **Income reconciliation tolerance** | Net salary versus bank credits | `±5%` (source) |
| **Ledger tolerance** | Gross versus Net + Deductions | `±2.00`, rupees assumed (source) |
| **Recovery passes per case** | Low-confidence recovery | `2` (preprocessing, second extractor) |
| **Salary variance limit** | `PROCEED_CONSERVATIVE` vs `REQUEST_RESUBMISSION` | *To be set; not defined in the source* |
| **Resubmission timeout** | Pending case to `CLOSE_UNRESOLVED` | *To be set; not defined in the source* |
| **Maximum resubmission attempts** | Guarantees every case terminates | *To be set; not defined in the source* |
| **Circuit-breaker limits** | Allowed drift from the rolling baseline (section 10) | *To be set; not defined in the source* |

*Cases that depend on a value marked "To be set" cannot be scored until it is fixed.*

### Automated Outcomes Metrics Suite

| Metric | Definition | Proposed target |
| :--- | :--- | :--- |
| `automation_rate` | Cases that reach an outcome (including `REQUEST_RESUBMISSION`) with no human touch ÷ all cases. | 100% |
| `stuck_case_rate` | Cases with no outcome, or pending past the timeout ÷ all cases. | 0 |
| `disposition_accuracy` | Cases whose outcome equals the expected outcome ÷ all cases. | 0.95 or higher |
| `false_accept_rate` | Cases whose outcome is less conservative than expected ÷ cases whose expected outcome is more conservative than `PROCEED`. | 0 on the benchmark |
| `false_reject_rate` | Cases whose outcome is more conservative than expected ÷ cases whose expected outcome is less conservative than `CLOSE_UNRESOLVED`. | Track the trend |
| `edge_case_containment` | Edge cases whose outcome is at least as conservative as expected ÷ edge cases (25 in the benchmark). | 25 of 25 |
| `conservative_value_error` | `PROCEED_CONSERVATIVE` cases where the value used exceeds the verified value ÷ `PROCEED_CONSERVATIVE` cases. | 0 |
| `recovery_rate` | Cases reaching `PROCEED` after recovery ÷ cases entering it. | Track the trend |
| `resubmission_resolution_rate` | Resubmission requests answered and resolved before timeout ÷ requests sent. | Track the trend |
| `auto_proceed_rate` | Cases ending `PROCEED` ÷ all cases; replaces `stp_rate`. | Informational |

- **Scoring notes:** False accepts and false rejects are scored on the conservativeness order in section 1. A metric whose denominator is empty is reported as `n/a`, not as 0 or 1.
- **Unchanged and label-free:** `gate_trigger_counts`, `mean_confidence`, `below_threshold_rate` and `provenance_coverage`; `below_threshold_rate` now measures how often recovery starts.
- **Retired:** `stp_rate` and `hitl_escalation_rate`.
- On the benchmark the expected `auto_proceed_rate` is the share of cases labeled `PROCEED`: at least 15 of 40 (37.5%), more if recoverable scans and spelling variants are labeled `PROCEED`. Do not push it up at the expense of `false_accept_rate`.

---

## 8. Current Baseline and Targets

Correctness baselines carry over from the original benchmark. The new metrics have no baseline until the automated flow is built and run, and recovery and recalibration may shift the extraction and calibration numbers, so re-run all of them after the change.

| Evaluation Metric | Baseline Value | Target Benchmark | Note |
| :--- | :---: | :---: | :--- |
| **Document Classification Accuracy** | 0.9938 (99.38%) | 0.950 or higher | Unchanged |
| **Classification Balanced Accuracy** | 0.9956 (99.56%) | 0.950 or higher | Unchanged |
| **Asymmetric Cost-Weighted Error** | 0.0124 | 0.150 or lower | Cost matrix incomplete |
| **Field Extraction Exact Match (EM)** | 0.9770 (97.70%) | 0.920 or higher | Unchanged |
| **Field Extraction Token F1 Score** | 0.9878 (98.78%) | 0.950 or higher | Unchanged |
| **OCR Character Error Rate (CER)** | 0.0142 (1.42%) | 0.030 or lower | Unchanged |
| **Contradiction Detection Recall (Safety)** | 1.0000 (100.00%) | 0.980 or higher | Too few cases to certify |
| **Contradiction Precision** | 1.0000 (100.00%) | 0.900 or higher | Unchanged |
| **Brier Score** | 0.0346 | 0.100 or lower | Unchanged |
| **Expected Calibration Error (ECE)** | 0.1489 reported; ~0.151 from bins | 0.150 or lower; proposed 0.050 | Re-run |
| **Straight-Through Processing (STP) Rate** | 0.3750 (37.50%) | None | **Retired** |
| **HITL Escalation Rate** | 0.6250 (62.50%) | None | **Retired** |
| **Automation Rate** | Not yet measured | 100% | **New** |
| **Stuck-Case Rate** | Not yet measured | 0 | **New** |
| **Disposition Accuracy** | Not yet measured | 0.95 or higher (proposed) | **New** |
| **Edge-Case Containment** | Not yet measured | 25 of 25 | **New** |
| **False-Accept Rate** | Not yet measured | 0 | **New** |
| **Gate-Passing Error Rate** | Not yet measured | 0 | **New** |

*These values are baseline results for the shipped benchmark dataset and should be interpreted as an engineering benchmark.*

---

## 9. Why This Metric Set Was Chosen

- **Safety:** Contradiction recall, false-accept rate, confusion matrices, and cost-weighted error emphasize the asymmetric harm of corrupted borrower financials.
- **Class fairness:** Balanced accuracy and macro metrics prevent payslip-heavy document distributions from hiding weak classification on rare deeds.
- **Extraction fidelity:** Exact Match, Token F1, and CER test whether granular entities and financial figures are extracted without distortion.
- **Trust in automation:** Brier, ECE, reliability bins, and the gate-passing error rate test whether confidence is reliable enough to be the only gate for `PROCEED`.
- **Automation health:** Automation rate, stuck-case rate, disposition accuracy, and recovery and resubmission rates show whether the agent resolves cases correctly on its own.
- **Auditability:** Provenance coverage guarantees full source verification rather than treating the LLM/OCR as an unverifiable authority.

---

## 10. Risks and Safeguards

The current benchmark cannot show that an unattended agent is safe; it can only show that nothing has failed yet.

- **Too few cases:** The baseline figures are consistent with 161 documents and a single error that cost 2 ($160 \div 161 = 0.9938$; $2 \div 161 = 0.0124$), so one document moves accuracy by about 0.6 points. With at most about 15 contradiction cases and no wrongly extracted cases, perfect scores say little about the true error rate. Grow the benchmark with adversarial and wrongly extracted cases and add historical underwritten outcomes.
- **Digital tampering is now required, not future scope:** A forged document that is internally consistent passes every check in this report, and no reviewer would see the splice. Quantify precision and recall on image splicing, font inconsistencies, and PDF metadata modifications.
- **Loosened matching:** An automated re-match can "resolve" a genuine conflict by relaxing the matcher. Limit it to deterministic normalizations and never lower the similarity threshold.
- **Sensitive data:** Unmasked Aadhaar numbers must be redacted before they reach provenance snippets, logs or the audit trail, not only in the final stored copy.
- **Downstream inheritance:** Credit and decision agents now receive data no person has looked at. Each `PROCEED_CONSERVATIVE` case must carry its flag forward, and a flagged value is treated as unverified.
- **Accountability:** The source describes this component as decision-support inside a human-in-the-loop architecture. Confirm with compliance that unattended operation is acceptable under the lender's own policy and the applicable RBI requirements before going live.

### Safeguards that do not block a case
- **Circuit breaker:** When `below_threshold_rate`, `gate_trigger_counts` or the resubmission rate drifts past its limit, stops issuing `PROCEED`, holds new cases in an automatic retry queue without contacting borrowers, and alerts engineering about the system (not about individual cases).
- **Full provenance and audit trail:** Recorded for every decision.
- **Optional after-the-fact sampling:** Sampling of auto-processed cases, which nothing waits on and whose results become production labels. The agent is fully automated without the sampling.

---

## 11. Future Evaluation Scope

- **Multilingual KYC extraction:** Benchmark performance across Hindi, Tamil, Telugu, and Marathi regional identity documents.
- **Per-segment slicing:** Evaluate performance by employer tier, income band, scan resolution, and bank statement format.
- **Latency and cost:** Tokens, wall-clock time, and OCR compute cost per multi-page document bundle, including the cost of recovery passes.
- **Resubmission simulation:** Replay borrower replies so the benchmark can score final outcomes as well as first-pass outcomes.

---

## 12. Implementation, Reproducibility & Governance Note

The existing commands still reproduce the baseline:
```bash
python -m src.evaluation.eval_cli
python -m src.evaluation.eval_cli --output evaluation_report.json
python -m pytest tests/ -v
```

The evaluation CLI described in the source reports the retired HITL metrics. The new metrics in section 7 need to be added to it, and the expected-outcome labels from section 2 added to the dataset. The agent's gate logic also has to change to implement the automated actions; this report specifies the metrics and does not change the code.

The Document Ingestion Agent remains an evidentiary extraction and reconciliation component, but in this version it acts without a reviewer. The $\pm 5\%$ tolerance, the salary variance limit, the cost matrix and every target marked as proposed are engineering choices; they should not be represented as official RBI rules or regulatory requirements.
