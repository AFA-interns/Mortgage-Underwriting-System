# DOCUMENT INGESTION AGENT
# Evaluation Metrics & Rationale

**Mortgage Underwriting System**  
*India-focused • Decision-support • Human-in-the-loop*

> **Purpose:** Document what each Document Ingestion Agent metric measures, why it was selected, and how it supports high-fidelity extraction, deterministic Indian regulatory validation, cross-document reconciliation, and safe human-in-the-loop routing.

---

## 1. Evaluation Context

The **Document Ingestion Agent (Agent 1 - Owner: Tejasva)** is evaluated as a hybrid neuro-symbolic extraction and reconciliation system. Its architecture performs:
1. **Multi-format Document Intake & Classification** (identifying PAN, Aadhaar, Salary Slips, Form 16, ITR, Bank Statements, Property Deeds, and Unknown files).
2. **Text & Tabular Extraction** using spatial PDF parsers (`PyMuPDF`, `pdfplumber`).
3. **Structured Field Extraction** into strongly typed Pydantic models with field-level provenance tracking.
4. **Deterministic Validation** against Indian banking, tax, and identity formats (PAN regex, Aadhaar masking, IFSC codes, and salary arithmetic).
5. **Cross-Document Reconciliation Matrix** (fuzzy name resolution across KYC/banking, employer consistency, payslip vs. bank deposit matching, and recurring EMI liability detection).
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

## 2. Dataset and Ground Truth

The benchmark evaluation dataset contains **40 labeled Indian home loan application bundles** comprising over **160 individual document files**. Ground-truth labels and field annotations are assigned independently by domain underwriters:

- **Class & Bundle Distribution**:
  - `15 Clean Prime Salaried` bundles (Aarav Sharma - TCS archetype: matching KYC, 3-month payslips, Form 16, 6-month HDFC statement, registered sale deed).
  - `8 Name Discrepancy & Alias` bundles (Priya Suresh Patel vs. Priya S. Patel vs. Priya Patel; initials and spelling variants).
  - `7 Income & Banking Variance` bundles (Vikram Malhotra archetype: payslip net pay ₹1.6L vs bank credit ₹85k; cash deposits; bonus distortions).
  - `6 Missing Mandatory Document` bundles (Rahul Verma archetype: missing Aadhaar KYC, 6-month bank statement, or property papers).
  - `4 Low-Quality Scan & Noise` bundles (thermal prints, skew, faded contrast, and artifacts).
- **Edge cases & Safety Gates**: Contradictions, arithmetic ledger mismatches, and unmasked Aadhaar formats are deliberately included to test safety guardrails.

---

## 3. Classification & Intake Metrics

Classification metrics evaluate whether uploaded borrower files are correctly assigned to their respective document categories.

### 3.1 Accuracy and Balanced Accuracy
$$\text{Accuracy} = \frac{\text{Correct Document Predictions}}{\text{Total Documents}}$$
$$\text{Balanced Accuracy} = \frac{1}{K} \sum_{k=1}^{K} \text{Recall}_k$$

- **Significance:** Accuracy gives a rapid global correctness measure, while balanced accuracy prevents common documents (such as monthly payslips) from concealing poor classification on rare, high-stakes documents (such as Form 16 Part A/B or Property Deeds).
- **Why Chosen:** Underwriting packages contain unequal class distributions (e.g., 3–6 salary slips per applicant vs. only 1 PAN card). Balanced accuracy guarantees that every document type is evaluated with equal importance.

### 3.2 Per-Class Precision, Recall, and F1
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}, \quad \text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}, \quad \text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

| Document Class | What Precision Tells Us | What Recall Tells Us |
| :--- | :--- | :--- |
| `PAN_CARD` | Guarantees tax identity is genuine; limits false KYC. | Ensures mandatory tax identity proof is not overlooked. |
| `AADHAAR_CARD` | Confirms valid resident UIDAI identification. | Ensures mandatory residential address proof is captured. |
| `SALARY_SLIP` | Prevents mislabeling unstructured letters as income proofs. | Ensures all submitted earnings periods are ingested. |
| `FORM_16` | Ensures annual employer tax certificates are verified. | Captures statutory annual income verification. |
| `BANK_STATEMENT` | Ensures complex financial ledgers are parsed properly. | Critical safety recall: prevents missing banking cash flows. |
| `PROPERTY_DEED` | Ensures legal title documents are routed to valuation. | Ensures property collateral data is never skipped. |

- **Why Chosen:** The business impact of misclassification is asymmetric. Misclassifying a Bank Statement as an arbitrary document can cause an unverified credit approval, making high Recall on financial proofs a critical safety requirement.

### 3.3 Confusion Matrix
Tabulates actual versus predicted document types across all 8 classes.
- **Why Chosen:** Discloses exact cross-classification patterns (e.g., whether Form 16 Part B is ever misclassified as an ITR-V) rather than reducing multi-class behavior to a single scalar.

### 3.4 Asymmetric Ingestion Cost Matrix
The evaluation applies the following prototype cost penalty matrix:

| Actual \ Predicted | `PAN` | `AADHAAR` | `SALARY_SLIP` | `FORM_16` | `BANK_STMT` | `PROPERTY` | `UNKNOWN` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BANK_STMT`** | 0 | 8 | 10 | 6 | 0 | 8 | 2 |
| **`PAN_CARD`** | 0 | 4 | 8 | 6 | 8 | 8 | 2 |
| **`AADHAAR`** | 4 | 0 | 8 | 6 | 8 | 8 | 2 |
| **`SALARY_SLIP`** | 8 | 8 | 0 | 3 | 10 | 8 | 2 |
| **`PROPERTY`** | 8 | 8 | 8 | 8 | 8 | 0 | 3 |

$$\text{Cost-Weighted Error} = \frac{1}{N} \sum \text{Cost}[\text{Actual}][\text{Predicted}]$$
- **Why Chosen:** Misclassifying a Bank Statement as a Salary Slip carries maximum penalty (10.0) because it risks poisoning the borrower's income and debt calculations. Conversely, classifying an ambiguous scan as `UNKNOWN` carries minimal cost (2.0) because it safely triggers human review.

---

## 4. Field-Level Extraction & OCR Metrics

Field-level metrics measure how accurately OCR and Pydantic extractors pull granular values from raw layouts.

### 4.1 Character Error Rate (CER) and Word Error Rate (WER)
$$\text{CER} = \frac{\text{LevenshteinDistance}(\text{Ref}_{\text{chars}}, \text{Pred}_{\text{chars}})}{N_{\text{ref\_chars}}}, \quad \text{WER} = \frac{\text{LevenshteinDistance}(\text{Ref}_{\text{words}}, \text{Pred}_{\text{words}})}{N_{\text{ref\_words}}}$$
- **Significance:** Measures raw text extraction fidelity from scanned or digital PDFs.
- **Why Chosen:** Low-quality scans or noise degrade field parsers. Tracking CER helps isolate whether an extraction failure was caused by OCR degradation or regex/parser logic.

### 4.2 Exact Match (EM) and Token F1 Score
- **Exact Match (EM):** Binary 1.0/0.0 score indicating whether the normalized extracted string matches the ground truth verbatim.
- **Token F1 Score:** Harmonic mean of precision and recall computed over bag-of-words tokens.
- **Why Chosen:** Exact Match is essential for discrete identifiers (PAN: `ABCPS1234F`, Aadhaar: `XXXX-XXXX-8921`, IFSC: `HDFC0001234`), while Token F1 accommodates minor word permutations in complex multi-word strings (e.g., Employer: `"Tata Consultancy Services Limited"` vs. `"Tata Consultancy Services Ltd"`).

### 4.3 Numeric Value Accuracy (Tolerance $\le \text{₹1.00}$)
$$\text{Numeric Accuracy} = \mathbb{I}(|\text{Value}_{\text{pred}} - \text{Value}_{\text{gt}}| \le \text{₹1.00})$$
- **Significance:** Verifies exact financial quantification for Gross Pay, Net Pay, PF, TDS, Bank Balance, and Consideration Value.
- **Why Chosen:** Mortgage debt-to-income (FOIR) and loan-to-value (LTV) ratios depend on exact rupees. Approximations or missing zeros are unacceptable.

### 4.4 Field Provenance Coverage & Precision
$$\text{Provenance Coverage} = \frac{\text{Extracted Fields with Valid (Doc, Page, Snippet) Provenance}}{\text{Total Extracted Fields}}$$
- **Significance:** Verifies that every extracted field links back to an exact source snippet and page number.
- **Why Chosen:** Essential for regulatory compliance, auditability, and explainable Human-in-the-Loop review. Underwriters must be able to click and verify every number in seconds.

---

## 5. Validation & Ledger Arithmetic Metrics

Validation metrics measure the agent's ability to verify domain constraints and ledger mathematics.

### 5.1 Deterministic Rule Pass Rate & False Rejection Rate
- Evaluates PAN format regex (`^[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]$`), 4th-character individual 'P' check, Aadhaar 12-digit masking, and bank IFSC formatting.
- **Why Chosen:** Indian regulatory compliance requires hard verification of statutory identity documents before credit appraisal.

### 5.2 Salary Ledger Arithmetic Reconciliation Rate
$$\text{Ledger Accuracy} = \mathbb{I}(|\text{Gross Salary} - (\text{Net Pay} + \text{Total Deductions})| \le \text{₹2.00})$$
- **Significance:** Validates internal ledger consistency on salary slips.
- **Why Chosen:** Fabricated or forged payslips frequently contain arithmetic mismatches between gross earnings and net take-home pay. This metric validates arithmetic integrity before data flows downstream.

---

## 6. Cross-Document Reconciliation Metrics

Reconciliation metrics evaluate the agent's ability to cross-verify data across separate documents.

### 6.1 Name Resolution F1 Score
Evaluates token-based fuzzy string matching across PAN, Aadhaar, Salary Slips, Bank Statements, and Property Deeds against ground-truth name equivalence.
- **Significance:** Indian loan applications frequently feature initials and name sequence variants (e.g., `"Priya Suresh Patel"` vs `"Priya S. Patel"`).
- **Why Chosen:** Distinguishes genuine alias variations (acceptable with high fuzzy score) from outright identity mismatches (which must be blocked).

### 6.2 Income vs. Bank Credit Reconciliation Accuracy
Verifies monthly net salary on payslips against monthly credit transactions in bank statements within $\pm 5\%$ tolerance.
- **Significance:** Detects undeclared salary deductions, exaggerated payslips, or payroll delays.
- **Why Chosen:** Comparing declared income against actual deposited cash flow is the most critical fraud-prevention step in mortgage underwriting.

### 6.3 Contradiction Detection Recall (Safety-Critical Recall)
$$\text{Contradiction Recall} = \frac{\text{True Contradictions Detected}}{\text{Total Actual Contradictions in Dataset}}$$
- **Significance:** Measures the percentage of true document conflicts (name mismatches, salary discrepancies, missing mandatory docs) caught by the agent.
- **Why Chosen:** **This is the single most critical safety metric for Document Ingestion.** A false negative (missing a contradiction) lets corrupted or fraudulent data poison the Credit and Decision agents. Target is $\ge 98.0\%$.

---

## 7. Confidence Calibration Metrics

Confidence calibration measures whether the agent's composite confidence score ($0.0 - 1.0$) reflects true extraction correctness.

### 7.1 Brier Score
$$\text{Brier Score} = \frac{1}{N} \sum_{i=1}^{N} (\text{Confidence}_i - \text{Correctness}_i)^2$$
- Lower is better; 0.0 is perfect calibration.
- **Why Chosen:** Penalizes overconfidence and rewards well-calibrated uncertainty.

### 7.2 Expected Calibration Error (ECE)
$$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
- **Significance:** Measures the weighted gap between average confidence and observed accuracy across confidence bins.
- **Why Chosen:** The Document Ingestion Agent uses $\text{Confidence} \ge 0.85$ as the gateway for automated straight-through processing. ECE tests whether predictions rated $\ge 0.85$ confidence actually achieve $\ge 85-90\%$ accuracy.

### 7.3 Reliability Bins
Reports sample count, mean confidence, actual accuracy, and calibration gap across 5 confidence intervals ($[0.0-0.2], [0.2-0.4], [0.4-0.6], [0.6-0.8], [0.8-1.0]$).
- **Why Chosen:** Visual diagnostic revealing whether overconfidence or underconfidence occurs in specific operational regimes.

---

## 8. Runtime & Operational Metrics

Operational metrics require no ground-truth labels and are computed from live audit logs to monitor system health in production:

| Metric | Definition / Significance | Why Chosen |
| :--- | :--- | :--- |
| `straight_through_processing_rate` | $\text{STP Rate} = 1 - \text{hitl\_escalation\_rate}$ | Measures automation efficiency and turnaround speed. |
| `hitl_escalation_rate` | $\text{Cases Routed to HITL} \div \text{Total Cases}$ | Measures human underwriter review workload. |
| `mean_confidence` | Average confidence across all processed applications. | Monitors evidence quality across loan batches. |
| `below_threshold_rate` | Share of applications with confidence $< 0.85$. | Shows how often the low-confidence safety gate fires. |
| `safety_gate_triggers` | Counts per gate (Missing Docs, Name Mismatch, Salary Variance, Math Error). | Pinpoints the primary cause of operational exceptions. |
| `provenance_completeness` | Rate of fields with verified source bounding snippets. | Ensures 100% auditability across production applications. |

---

## 9. Baseline Results on the Benchmark Dataset

Below are the empirical baseline results on the 40-case Indian mortgage evaluation dataset:

| Evaluation Metric | Baseline Value | Target Benchmark | Status |
| :--- | :---: | :---: | :---: |
| **Document Classification Accuracy** | **99.38%** | $\ge 95.0\%$ | Passed |
| **Balanced Classification Accuracy** | **99.56%** | $\ge 95.0\%$ | Passed |
| **Asymmetric Cost-Weighted Error** | **0.0124** | $\le 0.150$ | Passed |
| **Field Extraction Exact Match (EM)** | **97.70%** | $\ge 92.0\%$ | Passed |
| **Field Extraction Token F1 Score** | **98.78%** | $\ge 95.0\%$ | Passed |
| **OCR Character Error Rate (CER)** | **1.42%** | $\le 3.0\%$ | Passed |
| **Field Provenance Coverage** | **100.00%** | $100.0\%$ | Passed |
| **Contradiction Detection Recall (Safety)** | **100.00%** | $\ge 98.0\%$ | Passed |
| **Contradiction Precision** | **100.00%** | $\ge 90.0\%$ | Passed |
| **Name Resolution Accuracy** | **100.00%** | $\ge 95.0\%$ | Passed |
| **Brier Calibration Score** | **0.0346** | $\le 0.100$ | Passed |
| **Expected Calibration Error (ECE)** | **0.1489** | $\le 0.150$ | Passed |
| **Straight-Through Processing (STP) Rate** | **37.50%** | Baseline Mix | Normal |
| **HITL Review Escalation Rate** | **62.50%** | Safety Guardrail | Normal |

---

## 10. Why This Metric Set Was Chosen

1. **Downstream Safety First:** A failure in Document Ingestion poisons all downstream calculations (DTI, FOIR, LTV). High Contradiction Recall ($100\%$) and asymmetric cost weighting protect the Credit and Decision agents from false data.
2. **Explainability & Provenance:** By requiring 100% Provenance Coverage, every number displayed to human underwriters is traceable to its source document page and snippet.
3. **Calibrated Trust in Automation:** Brier and ECE scores verify that the $0.85$ confidence threshold is mathematically trustworthy for straight-through processing.
4. **Class & Document Fairness:** Balanced accuracy ensures that less frequent documents (e.g., Form 16 Part B, Property Deeds) perform with the same high rigor as salary slips.

---

## 11. Implementation & Reproducibility

The complete evaluation suite can be reproduced directly using the project evaluation CLI:

```bash
# Run benchmark evaluation across all 40 labeled cases
python -m src.evaluation.eval_cli

# Save detailed JSON evaluation report
python -m src.evaluation.eval_cli --output evaluation_report.json

# Run unit tests
python -m pytest tests/ -v
```

---

## 12. Scope & Governance Note

The **Document Ingestion Agent** is an evidentiary extraction and reconciliation component within a human-in-the-loop home loan underwriting system. It performs factual extraction and validation; it does not evaluate creditworthiness or make loan approval decisions. Prototype weights, tolerance thresholds ($\pm 5\%$), and cost matrices are engineering evaluation choices designed to ensure robustness, compliance, and safety.
