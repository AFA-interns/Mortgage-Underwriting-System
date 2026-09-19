"""
Document Ingestion Agent - Core Orchestrator & LangGraph Node.
Executes the full 7-step document ingestion workflow:
1. Intake & Classification
2. Pre-processing
3. Text & Layout Extraction
4. Structured Field Extraction
5. Field Validation
6. Cross-Document Reconciliation
7. Confidence Scoring & Human-Review Routing
Produces the standardized output state for downstream Credit & Property Agents.
"""

import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from app.models.document_ingestion import (
    DocumentType,
    DocumentMetadata,
    PANCardData,
    AadhaarCardData,
    SalarySlipData,
    Form16Data,
    ITRVData,
    BankStatementData,
    PropertyDocData,
)
from app.models.document_ingestion_state import (
    DocumentIngestionOutput,
    MortgageUnderwritingState,
    BorrowerKYCProfile,
    BorrowerIncomeProfile,
    BorrowerLiabilitiesProfile,
    PropertyProfile,
)
from app.document_ingestion.preprocessor import DocumentPreprocessor, PreprocessedDocument
from app.document_ingestion.classifier import DocumentClassifier
from app.document_ingestion.extractors import DocumentExtractors
from app.document_ingestion.validators import IndianDocumentValidators
from app.document_ingestion.reconciliation import CrossDocumentReconciler
from app.document_ingestion.confidence import ConfidenceEvaluator


class DocumentIngestionAgent:
    """Agentic AI Engine for Mortgage Document Ingestion & Verification."""

    @classmethod
    def process_document_bundle(
        cls,
        file_paths: List[str],
        application_id: str = "APP-2026-IND-001",
        borrower_id: str = "BORR-2026-001",
    ) -> DocumentIngestionOutput:
        """
        Runs the complete 7-step ingestion workflow across a bundle of borrower documents.
        """
        audit_log: List[str] = []
        audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Started ingestion for Application ID: {application_id}")

        # Entities extracted
        pan_data: Optional[PANCardData] = None
        aadhaar_data: Optional[AadhaarCardData] = None
        salary_slips: List[SalarySlipData] = []
        form_16: Optional[Form16Data] = None
        itr_v: Optional[ITRVData] = None
        bank_statement: Optional[BankStatementData] = None
        property_doc: Optional[PropertyDocData] = None
        docs_metadata: List[DocumentMetadata] = []

        # =============================================================
        # STEPS 1-4: Intake, Preprocess, Classify, Extract
        # =============================================================
        for idx, path in enumerate(file_paths):
            if not os.path.exists(path):
                audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: File not found: {path}")
                continue

            # Step 2: Preprocess & Text Layer Extraction
            prep_doc = DocumentPreprocessor.process_file(path)
            
            # Step 1: Classify Document
            doc_type, class_conf = DocumentClassifier.classify(prep_doc)
            
            doc_meta = DocumentMetadata(
                document_id=f"DOC-{idx+1:03d}",
                original_filename=prep_doc.filename,
                classified_type=doc_type,
                classification_confidence=class_conf,
                page_count=prep_doc.page_count,
                file_size_bytes=prep_doc.metadata.get("file_size_bytes", 0),
                extracted_text_snippet=prep_doc.raw_text[:200].strip() if prep_doc.raw_text else "No text extracted",
                processing_status="SUCCESS",
            )
            docs_metadata.append(doc_meta)
            audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Classified '{prep_doc.filename}' as {doc_type.value} (Conf: {class_conf * 100:.1f}%)")

            # Step 4: Structured Field Extraction
            if doc_type == DocumentType.PAN_CARD:
                pan_data = DocumentExtractors.extract_pan(prep_doc)
            elif doc_type == DocumentType.AADHAAR_CARD:
                aadhaar_data = DocumentExtractors.extract_aadhaar(prep_doc)
            elif doc_type == DocumentType.SALARY_SLIP:
                slip = DocumentExtractors.extract_salary_slip(prep_doc)
                salary_slips.append(slip)
            elif doc_type == DocumentType.FORM_16:
                form_16 = DocumentExtractors.extract_form_16(prep_doc)
            elif doc_type == DocumentType.ITR:
                itr_v = DocumentExtractors.extract_itr(prep_doc)
            elif doc_type == DocumentType.BANK_STATEMENT:
                bank_statement = DocumentExtractors.extract_bank_statement(prep_doc)
            elif doc_type == DocumentType.PROPERTY_DEED:
                property_doc = DocumentExtractors.extract_property_deed(prep_doc)

        # =============================================================
        # STEP 5: Field Validation
        # =============================================================
        audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing deterministic domain validators...")
        
        # Validate PAN
        if pan_data:
            pan_val = IndianDocumentValidators.validate_pan(pan_data.pan_number)
            pan_data.is_valid_format = pan_val.is_valid
            audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] PAN Validation: {pan_val.message}")

        # Validate Aadhaar
        if aadhaar_data:
            aadh_val = IndianDocumentValidators.validate_aadhaar(aadhaar_data.aadhaar_number)
            aadhaar_data.is_valid_format = aadh_val.is_valid
            audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Aadhaar Validation: {aadh_val.message}")

        # Validate Salary Slips Arithmetic
        for s in salary_slips:
            sal_val = IndianDocumentValidators.validate_salary_arithmetic(
                gross_salary=s.gross_salary,
                net_salary=s.net_salary,
                total_deductions=s.total_deductions,
            )
            s.is_arithmetically_valid = sal_val.is_valid
            audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Salary Math ({s.month_year}): {sal_val.message}")

        # Validate Bank IFSC
        if bank_statement and bank_statement.ifsc_code:
            ifsc_val = IndianDocumentValidators.validate_ifsc(bank_statement.ifsc_code)
            bank_statement.is_valid_format = ifsc_val.is_valid
            audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Bank IFSC Validation: {ifsc_val.message}")

        # =============================================================
        # STEP 6: Cross-Document Reconciliation
        # =============================================================
        audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing multi-document cross-reconciliation...")
        reconciliation_report = CrossDocumentReconciler.reconcile(
            pan_data=pan_data,
            aadhaar_data=aadhaar_data,
            salary_slips=salary_slips,
            form_16=form_16,
            bank_statement=bank_statement,
            property_doc=property_doc,
        )
        audit_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Cross-Reconciliation Score: {reconciliation_report.reconciliation_score * 100:.1f}% "
            f"({reconciliation_report.total_contradictions_count} contradictions flagged)"
        )

        # =============================================================
        # STEP 7: Completeness, Confidence Scoring & HITL Routing
        # =============================================================
        checklist = ConfidenceEvaluator.evaluate_completeness(
            pan=pan_data,
            aadhaar=aadhaar_data,
            salary_slips=salary_slips,
            form_16=form_16,
            itr=itr_v,
            bank_statement=bank_statement,
            property_doc=property_doc,
        )

        confidence_breakdown = ConfidenceEvaluator.calculate_confidence(
            docs_metadata=docs_metadata,
            pan=pan_data,
            aadhaar=aadhaar_data,
            salary_slips=salary_slips,
            form_16=form_16,
            bank_statement=bank_statement,
            property_doc=property_doc,
            reconciliation_report=reconciliation_report,
            checklist=checklist,
        )

        human_review = ConfidenceEvaluator.evaluate_human_review(
            confidence=confidence_breakdown,
            checklist=checklist,
            reconciliation_report=reconciliation_report,
            pan=pan_data,
            salary_slips=salary_slips,
            bank_statement=bank_statement,
        )

        audit_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Overall Confidence: {confidence_breakdown.overall_confidence * 100:.1f}% "
            f"({confidence_breakdown.confidence_level}) | Human Review Required: {human_review.requires_human_review} (Priority: {human_review.review_priority})"
        )

        # =============================================================
        # Prepare Standard Packages for Downstream Agents
        # =============================================================
        # 1. Primary KYC Profile (for Credit & Compliance)
        primary_name = (
            (pan_data.full_name if pan_data and pan_data.full_name else None) or
            (aadhaar_data.full_name if aadhaar_data and aadhaar_data.full_name else None) or
            (salary_slips[0].employee_name if salary_slips and salary_slips[0].employee_name else "Applicant")
        )
        borrower_kyc = BorrowerKYCProfile(
            primary_name=primary_name,
            pan_number=pan_data.pan_number if pan_data else None,
            aadhaar_masked=aadhaar_data.aadhaar_number if aadhaar_data else None,
            dob=pan_data.dob if pan_data else (aadhaar_data.dob if aadhaar_data else None),
            gender=aadhaar_data.gender if aadhaar_data else None,
            residential_address=aadhaar_data.address if aadhaar_data else None,
            pincode=aadhaar_data.pincode if aadhaar_data else None,
        )

        # 2. Income Profile (for Credit Agent)
        avg_gross = (sum(s.gross_salary for s in salary_slips) / len(salary_slips)) if salary_slips else (form_16.gross_salary_sec17_1 / 12.0 if form_16 else 0.0)
        avg_net = (sum(s.net_salary for s in salary_slips) / len(salary_slips)) if salary_slips else 0.0
        employer_name = (salary_slips[0].employer_name if salary_slips else None) or (form_16.employer_name if form_16 else None)
        designation = salary_slips[0].designation if salary_slips else None

        borrower_income = BorrowerIncomeProfile(
            employer_name=employer_name,
            designation=designation,
            monthly_gross_salary=round(avg_gross, 2),
            monthly_net_salary=round(avg_net, 2),
            annual_gross_income_form16=form_16.gross_salary_sec17_1 if form_16 else (avg_gross * 12.0),
            annual_taxable_income=form_16.taxable_income if form_16 else 0.0,
            salary_slips_provided_count=len(salary_slips),
            average_bank_salary_credit=bank_statement.average_monthly_salary_credit if bank_statement else 0.0,
            income_stability_status="STABLE" if len(salary_slips) >= 3 and not reconciliation_report.contradictions else "REQUIRES_VERIFICATION",
        )

        # 3. Liabilities Profile (for Credit Agent)
        loan_records = []
        if bank_statement:
            for l in bank_statement.recurring_loan_emis:
                loan_records.append({"date": l.date, "description": l.description, "amount": l.amount})

        borrower_liabilities = BorrowerLiabilitiesProfile(
            detected_monthly_emis=bank_statement.total_monthly_obligations if bank_statement else 0.0,
            active_loan_count_detected=len(bank_statement.recurring_loan_emis) if bank_statement else 0,
            cheque_bounce_count_6m=bank_statement.bounce_cheque_count if bank_statement else 0,
            loan_debit_records=loan_records,
        )

        # 4. Property Profile (for Property Valuation Agent)
        prop_profile = None
        if property_doc:
            prop_profile = PropertyProfile(
                property_title=property_doc.document_title,
                property_address=property_doc.property_address,
                city=property_doc.city,
                pincode=property_doc.pincode,
                property_type=property_doc.property_type,
                super_builtup_area_sqft=property_doc.super_builtup_area_sqft,
                carpet_area_sqft=property_doc.carpet_area_sqft,
                purchase_or_market_value=property_doc.purchase_or_market_value,
                seller_or_builder_name=property_doc.seller_or_builder_name,
                buyer_or_owner_name=property_doc.buyer_or_owner_name,
                registration_number=property_doc.registration_number,
            )

        audit_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Document Ingestion completed successfully.")

        return DocumentIngestionOutput(
            application_id=application_id,
            borrower_id=borrower_id,
            documents_metadata=docs_metadata,
            pan_card=pan_data,
            aadhaar_card=aadhaar_data,
            salary_slips=salary_slips,
            form_16=form_16,
            itr_v=itr_v,
            bank_statement=bank_statement,
            property_document=property_doc,
            borrower_kyc=borrower_kyc,
            borrower_income=borrower_income,
            borrower_liabilities=borrower_liabilities,
            property_profile=prop_profile,
            checklist=checklist,
            reconciliation=reconciliation_report,
            confidence=confidence_breakdown,
            human_review=human_review,
            audit_log=audit_log,
        )


# -------------------------------------------------------------
# LangGraph Workflow Node Integration
# -------------------------------------------------------------
def document_ingestion_node(state: Union[MortgageUnderwritingState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Standard LangGraph node signature for Document Ingestion Agent.
    Accepts state containing `raw_document_paths` and `application_id`,
    executes the ingestion pipeline, and returns updated state for Credit & Property nodes.
    """
    if isinstance(state, dict):
        raw_paths = state.get("raw_document_paths", [])
        app_id = state.get("application_id", "APP-2026-IND-001")
        borrower_id = state.get("borrower_id", "BORR-2026-001")
    else:
        raw_paths = state.raw_document_paths
        app_id = state.application_id
        borrower_id = state.borrower_id or "BORR-2026-001"

    output = DocumentIngestionAgent.process_document_bundle(
        file_paths=raw_paths,
        application_id=app_id,
        borrower_id=borrower_id,
    )

    next_step = "HUMAN_IN_THE_LOOP" if output.human_review.requires_human_review and output.human_review.review_priority == "CRITICAL" else "CREDIT_AND_PROPERTY_ANALYSIS"
    status = "HITL_PENDING" if output.human_review.requires_human_review and output.human_review.review_priority == "CRITICAL" else "IN_PROGRESS"

    return {
        "application_id": app_id,
        "borrower_id": borrower_id,
        "raw_document_paths": raw_paths,
        "doc_ingestion_output": output.model_dump(),
        "current_step": next_step,
        "status": status,
    }
