"""
Confidence Scoring and Human-in-the-Loop (HITL) Routing Module.
Calculates multi-dimensional confidence breakdown, evaluates completeness against
mandatory document checklists, and triggers Human Underwriter review.
"""

from typing import List, Dict, Optional, Tuple, Any
from src.models.schemas import (
    PANCardData,
    AadhaarCardData,
    SalarySlipData,
    Form16Data,
    ITRVData,
    BankStatementData,
    PropertyDocData,
    DocumentMetadata,
)
from src.models.state import (
    ConfidenceBreakdown,
    MissingDocumentsCheck,
    HumanReviewRouting,
    CrossDocumentReconciliationReport,
)


class ConfidenceEvaluator:
    """Evaluates ingestion confidence and determines Human-in-the-Loop triggers."""

    @classmethod
    def evaluate_completeness(
        cls,
        pan: Optional[PANCardData],
        aadhaar: Optional[AadhaarCardData],
        salary_slips: List[SalarySlipData],
        form_16: Optional[Form16Data],
        itr: Optional[ITRVData],
        bank_statement: Optional[BankStatementData],
        property_doc: Optional[PropertyDocData],
    ) -> MissingDocumentsCheck:
        missing: List[str] = []

        has_pan = bool(pan and pan.pan_number)
        has_aadhaar = bool(aadhaar and aadhaar.aadhaar_number)
        has_salary = bool(salary_slips and len(salary_slips) > 0)
        has_f16 = bool(form_16 and form_16.gross_salary_sec17_1 > 0)
        has_itr = bool(itr and itr.gross_total_income > 0)
        has_bank = bool(bank_statement and bank_statement.account_number)
        has_prop = bool(property_doc and (property_doc.property_address or property_doc.purchase_or_market_value))

        if not has_pan:
            missing.append("PAN Card (Mandatory KYC)")
        if not has_aadhaar:
            missing.append("Aadhaar Card (Mandatory KYC & Address Proof)")
        if not has_salary and not has_f16 and not has_itr:
            missing.append("Income Proof (Salary Slips / Form 16 / ITR)")
        if not has_bank:
            missing.append("Bank Account Statement (6 Months Mandatory)")
        if not has_prop:
            missing.append("Property Documents (Sale Deed / Allotment Letter)")

        is_complete = len(missing) == 0

        return MissingDocumentsCheck(
            has_pan=has_pan,
            has_aadhaar=has_aadhaar,
            has_salary_slips=has_salary,
            salary_slip_count=len(salary_slips),
            has_form_16=has_f16,
            has_itr=has_itr,
            has_bank_statement=has_bank,
            bank_statement_months=bank_statement.months_covered if bank_statement else 0,
            has_property_docs=has_prop,
            missing_mandatory_documents=missing,
            is_complete=is_complete,
        )

    @classmethod
    def calculate_confidence(
        cls,
        docs_metadata: List[DocumentMetadata],
        pan: Optional[PANCardData],
        aadhaar: Optional[AadhaarCardData],
        salary_slips: List[SalarySlipData],
        form_16: Optional[Form16Data],
        bank_statement: Optional[BankStatementData],
        property_doc: Optional[PropertyDocData],
        reconciliation_report: CrossDocumentReconciliationReport,
        checklist: MissingDocumentsCheck,
    ) -> ConfidenceBreakdown:
        # 1. OCR / Extraction Quality Score
        if docs_metadata:
            ocr_scores = [d.classification_confidence for d in docs_metadata]
            ocr_quality_score = sum(ocr_scores) / len(ocr_scores)
        else:
            ocr_quality_score = 0.50

        # 2. Field Validation Score
        validation_passes = 0
        validation_total = 0

        if pan:
            validation_total += 1
            if pan.is_valid_format:
                validation_passes += 1

        if aadhaar:
            validation_total += 1
            if aadhaar.is_valid_format:
                validation_passes += 1

        if salary_slips:
            for s in salary_slips:
                validation_total += 1
                if s.is_arithmetically_valid:
                    validation_passes += 1

        if form_16:
            validation_total += 1
            if form_16.is_valid_format:
                validation_passes += 1

        if bank_statement:
            validation_total += 1
            if bank_statement.is_valid_format:
                validation_passes += 1

        field_validation_score = (validation_passes / validation_total) if validation_total > 0 else 0.50

        # 3. Cross-Reconciliation Score
        cross_reconciliation_score = reconciliation_report.reconciliation_score

        # 4. Completeness Score (5 core requirements)
        total_reqs = 5
        passed_reqs = 5 - len(checklist.missing_mandatory_documents)
        completeness_score = max(0.0, passed_reqs / total_reqs)

        # 5. Composite Weighted Overall Confidence
        overall_confidence = (
            (0.15 * ocr_quality_score) +
            (0.30 * field_validation_score) +
            (0.35 * cross_reconciliation_score) +
            (0.20 * completeness_score)
        )
        overall_confidence = round(min(1.0, max(0.0, overall_confidence)), 3)

        if overall_confidence >= 0.85:
            confidence_level = "HIGH"
        elif overall_confidence >= 0.70:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        return ConfidenceBreakdown(
            ocr_quality_score=round(ocr_quality_score, 3),
            field_validation_score=round(field_validation_score, 3),
            cross_reconciliation_score=round(cross_reconciliation_score, 3),
            completeness_score=round(completeness_score, 3),
            overall_confidence=overall_confidence,
            confidence_level=confidence_level,
        )

    @classmethod
    def evaluate_human_review(
        cls,
        confidence: ConfidenceBreakdown,
        checklist: MissingDocumentsCheck,
        reconciliation_report: CrossDocumentReconciliationReport,
        pan: Optional[PANCardData],
        salary_slips: List[SalarySlipData],
        bank_statement: Optional[BankStatementData],
    ) -> HumanReviewRouting:
        reasons: List[str] = []
        actions: List[str] = []
        priority = "NONE"

        # Check missing mandatory docs
        if not checklist.is_complete:
            reasons.append(f"Missing mandatory documents: {', '.join(checklist.missing_mandatory_documents)}")
            actions.append("Request missing mandatory documents from loan applicant.")
            priority = "HIGH"

        # Check contradictions
        if reconciliation_report.contradictions:
            for c in reconciliation_report.contradictions:
                reasons.append(f"Contradiction flagged: {c}")
            actions.append("Manual underwriter review required to verify name / income discrepancies.")
            if priority != "CRITICAL":
                priority = "HIGH"

        # Check salary arithmetic issues
        if salary_slips:
            for i, s in enumerate(salary_slips):
                if not s.is_arithmetically_valid and s.gross_salary > 0:
                    reasons.append(f"Payslip #{i+1} ({s.month_year}) arithmetic inconsistency between Gross, Deductions, and Net pay.")
                    actions.append("Cross-check original physical/PDF payslip line items.")
                    if priority == "NONE":
                        priority = "MEDIUM"

        # Check bank statement bounces
        if bank_statement and bank_statement.bounce_cheque_count > 0:
            reasons.append(f"Detected {bank_statement.bounce_cheque_count} inward ECS/cheque bounce(s) in bank statement.")
            actions.append("Escalate banking behavior to Credit Risk Analyst.")
            if priority == "NONE":
                priority = "MEDIUM"

        # Check low overall confidence
        if confidence.overall_confidence < 0.85:
            reasons.append(f"Overall extraction confidence ({confidence.overall_confidence * 100:.1f}%) is below 85% threshold.")
            actions.append("Conduct comprehensive Human-in-the-Loop document inspection.")
            if priority in ["NONE", "LOW"]:
                priority = "MEDIUM"

        requires_review = len(reasons) > 0
        if not requires_review:
            priority = "NONE"

        return HumanReviewRouting(
            requires_human_review=requires_review,
            review_priority=priority,
            reasons=reasons,
            suggested_actions=actions,
        )
