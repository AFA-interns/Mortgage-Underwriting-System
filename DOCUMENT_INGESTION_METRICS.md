# DOCUMENT INGESTION AGENT
# Evaluation Metrics & Rationale

**Mortgage Underwriting System**
*India-focused · Decision-support · Human-in-the-loop*

> **Purpose:** Document what each Document Ingestion Agent metric measures, why it was selected, and how it supports high-fidelity extraction, deterministic Indian regulatory validation, cross-document reconciliation, and safe human-in-the-loop routing.

---

## 1. Evaluation Context

The **Document Ingestion Agent** (`backend/app/document_ingestion/`) is evaluated as a hybrid neuro-symbolic extraction and reconciliation system. Its architecture performs:
1. **Multi-format Document Intake & Classification** (identifying PAN, Aadhaar, Salary Slips, Form 16, ITR, Bank Statements, Property Deeds, and Unknown files).
2. **Text & Tabular Extraction** using spatial PDF parsers (`PyMuPDF`, `pdfplumber`).
3. **Structured Field Extraction** into strongly typed Pydantic models with field-level provenance tracking.
4. **Deterministic Validation** against Indian banking, tax, and identity formats (PAN regex, Aadhaar masking, IFSC codes, and salary arithmetic).
5. **Cross-Document Reconciliation Matrix** (fuzzy name resolution across KYC/banking, employer consistency, payslip vs. bank deposit matching).
6. **Confidence Calibration & Human-in-the-Loop (HITL) Safety Gate Finalization**.

For each submitted loan application bundle, the key outputs produced are:

| Output | Range / Type | Meaning / Downstream Role |
| :--- | :---: | :--- |
| `document_type` | Enum (8 classes) | Classified document category (PAN, Aadhaar, Payslip, Form 16, ITR, Bank, Property, Unknown). |
| `field_extractions` | Typed Pydantic Objects | Extracted borrower KYC, income figures, banking aggregates, and property specifications. |
| `provenance` | Document + Page + Text Snippet | Auditability trail establishing exact source evidence for every extracted value. |
| `is_valid_format` | Boolean (per field/rule) | Deterministic pass/fail against Indian regulatory standards (PAN, Aadhaar, IFSC, Math). |
| `reconciliation_score` | 0.0 – 1.0 | Degree of consistency across multi-document entity pairs. |
| `contradictions` | List of Strings | Explicit discrepancies flagged (e.g. name mismatch, salary vs bank credit variance). |
| `overall_confidence` | 0.0 – 1.0 | Composite evidence extraction reliability score (threshold $\ge 0.85$ for auto-proceed). |
| `requires_human_review` | Boolean & Priority | Safety gate routing cases with low confidence, missing mandatory docs, or contradictions to human underwriters. |

Two metric families are therefore required:
1. **Correctness & Extraction Quality Metrics**: Compare classifications, extracted field tokens, arithmetic validation, and reconciliation findings against labeled ground truth.
2. **Runtime / Operational Metrics**: Measure throughput, straight-through processing (STP) rate, safety gate trigger distributions, and confidence stability from live audit trails without requiring labels.

---

## 2. Classification & Intake Metrics

Classification metrics evaluate whether uploaded borrower files are correctly assigned to their respective document categories.

### 2.1 Accuracy and Balanced Accuracy
$$\text{Accuracy} = \frac{\text{Correct Document Predictions}}{\text{Total Documents}}$$
$$\text{Balanced Accuracy} = \frac{1}{K} \sum_{k=1}^{K} \text{Recall}_k$$

- **Significance:** Accuracy gives a rapid global correctness measure, while balanced accuracy prevents common documents (such as monthly payslips) from concealing poor classification on rare, high-stakes documents (such as Form 16 or Property Deeds).
- **Why Chosen:** Underwriting packages contain unequal class distributions (e.g., 3–6 salary slips per applicant vs. only 1 PAN card). Balanced accuracy guarantees that every document type is evaluated with equal importance.

### 2.2 Per-Class Precision, Recall, and F1
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}, \quad \text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}, \quad \text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

- **Why Chosen:** The business impact of misclassification is asymmetric. Misclassifying a Bank Statement as an arbitrary document can cause an unverified credit approval, making high Recall on financial proofs a critical safety requirement.

### 2.3 Asymmetric Ingestion Cost Matrix
A prototype cost penalty matrix weights misclassifications by downstream risk (e.g., misreading a Bank Statement as a Salary Slip costs far more than misreading an ambiguous scan as `UNKNOWN`, which safely triggers human review instead of poisoning income figures).
$$\text{Cost-Weighted Error} = \frac{1}{N} \sum \text{Cost}[\text{Actual}][\text{Predicted}]$$

---

## 3. Field-Level Extraction & OCR Metrics

### 3.1 Character Error Rate (CER) and Word Error Rate (WER)
$$\text{CER} = \frac{\text{LevenshteinDistance}(\text{Ref}_{\text{chars}}, \text{Pred}_{\text{chars}})}{N_{\text{ref\_chars}}}, \quad \text{WER} = \frac{\text{LevenshteinDistance}(\text{Ref}_{\text{words}}, \text{Pred}_{\text{words}})}{N_{\text{ref\_words}}}$$
- **Why Chosen:** Low-quality scans or noise degrade field parsers. Tracking CER helps isolate whether an extraction failure was caused by OCR degradation or regex/parser logic.

### 3.2 Exact Match (EM) and Token F1 Score
- **Exact Match (EM):** Binary 1.0/0.0 score indicating whether the normalized extracted string matches the ground truth verbatim.
- **Token F1 Score:** Harmonic mean of precision and recall computed over bag-of-words tokens.
- **Why Chosen:** Exact Match is essential for discrete identifiers (PAN, Aadhaar, IFSC), while Token F1 accommodates minor word permutations in multi-word strings (e.g., `"Tata Consultancy Services Limited"` vs. `"Tata Consultancy Services Ltd"`).

### 3.3 Numeric Value Accuracy (Tolerance ≤ ₹1.00)
$$\text{Numeric Accuracy} = \mathbb{I}(|\text{Value}_{\text{pred}} - \text{Value}_{\text{gt}}| \le \text{₹1.00})$$
- **Why Chosen:** Mortgage debt-to-income (FOIR) and loan-to-value (LTV) ratios depend on exact rupees. Approximations or missing zeros are unacceptable.

---

## 4. Cross-Document Reconciliation Metrics

### 4.1 Contradiction Detection Recall (Safety-Critical Recall)
$$\text{Contradiction Recall} = \frac{\text{True Contradictions Detected}}{\text{Total Actual Contradictions in Dataset}}$$
- **Significance:** This is the single most critical safety metric for Document Ingestion. A false negative (missing a contradiction) lets corrupted or fraudulent data poison the Credit and Decision agents.

### 4.2 Name Resolution & Income Reconciliation Accuracy
Evaluates token-based fuzzy string matching across PAN, Aadhaar, Salary Slips, Bank Statements, and Property Deeds against ground-truth name equivalence, and verifies monthly net salary on payslips against bank credit within a tolerance band.

---

## 5. Confidence Calibration Metrics

### 5.1 Brier Score
$$\text{Brier Score} = \frac{1}{N} \sum_{i=1}^{N} (\text{Confidence}_i - \text{Correctness}_i)^2$$
Lower is better; 0.0 is perfect calibration. Penalizes overconfidence and rewards well-calibrated uncertainty.

### 5.2 Expected Calibration Error (ECE) and Reliability Bins
$$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
The agent uses $\text{Confidence} \ge 0.85$ as the gateway for automated straight-through processing; ECE tests whether predictions rated $\ge 0.85$ confidence actually achieve comparably high accuracy.

---

## 6. Runtime & Operational Metrics

Computed from live audit logs, no ground-truth labels required:

| Metric | Definition |
| :--- | :--- |
| `straight_through_processing_rate` | $1 - \text{hitl\_escalation\_rate}$ |
| `hitl_escalation_rate` | Cases routed to HITL ÷ total cases |
| `mean_confidence` | Average confidence across all processed applications |
| `below_threshold_rate` | Share of applications with confidence < 0.85 |
| `safety_gate_triggers` | Counts per gate (missing docs, name mismatch, income discrepancy, etc.) |

---

## 7. Implementation

All of the above are implemented as pure, tested functions in `backend/app/document_ingestion/metrics.py` (`compute_classification_metrics`, `compute_cost_weighted_error`, `compute_cer`/`compute_wer`, `compute_exact_match`/`compute_token_f1`, `compute_numeric_accuracy`, `compute_brier_score`/`compute_ece`, `compute_reconciliation_metrics`, `compute_operational_metrics`) — see `backend/tests/test_document_ingestion_metrics.py` for hand-computed correctness checks on each one.

### 7.1 Results — bundled demo scenarios (real, small sample)

Reproduce with `cd backend && venv\Scripts\python.exe scripts/document_ingestion_metrics_report.py`. This runs the real agent (`DocumentIngestionAgent.process_document_bundle`) against this project's own 6 bundled demo scenarios — clean prime, name discrepancy, salary/bank discrepancy, missing documents, correctable PAN error, and the image-upload (OCR) demo — **35 documents total**, labeled against this project's own known, hand-written ground truth (not an external or crowd-labeled dataset). This is deliberately small — a real measurement from this project's own fixtures, not a claim of broad real-world coverage. A larger benchmark would need a bigger, independently labeled document set.

| Metric | Result |
| :--- | :---: |
| Document Classification Accuracy / Balanced Accuracy | 100.0% / 100.0% (35/35 documents, all 6 classes) |
| Asymmetric Cost-Weighted Error | 0.0000 |
| Contradiction Detection Recall / Precision | 100.0% / 100.0% (2/2 planted contradictions caught, no false alarms) |
| Name Resolution Accuracy | 100.0% |
| Salary ↔ Bank Reconciliation Accuracy | 100.0% (4 bundles with a bank statement to reconcile against) |
| Brier Calibration Score | 0.0210 |
| Expected Calibration Error (ECE, 5 bins) | 0.1153 |
| Straight-Through Processing (STP) Rate | 33.3% (2 of 6 bundles needed no review) |
| HITL Escalation Rate | 66.7% (4 of 6 — by design, most of these demo bundles exist to exercise a safety gate) |
| HITL Routing Decision Accuracy | 100.0% (6/6 bundles routed correctly vs. their known expected outcome) |
| Field-level checks (clean-prime bundle, exact known values) | PAN exact match 1.0, borrower name token-F1 1.0, gross salary / bank AMB numeric match 1.0 |

One finding worth calling out: the `correctable_pan_error` bundle's PAN *card* is correctly classified (document type), but its mandatory-document checklist still flags PAN as missing — because the extracted PAN number fails format validation, and the checklist only counts a document type as "present" when the value it carries is actually usable as KYC proof. That's the agent's safety behavior working as intended, not a classification error.

**Scope note:** this is a real but small benchmark (6 bundles the project ships for its own demos), not a large independently-labeled dataset — unlike the earlier draft of this document, nothing above is simulated or hand-typed per category.

---

## 8. Scope & Governance Note

The **Document Ingestion Agent** is an evidentiary extraction and reconciliation component within a human-in-the-loop home loan underwriting system. It performs factual extraction and validation; it does not evaluate creditworthiness or make loan approval decisions. Tolerance thresholds (e.g. ±5% income variance) and cost matrices are engineering evaluation choices designed to ensure robustness, compliance, and safety.
