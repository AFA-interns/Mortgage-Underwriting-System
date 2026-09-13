import os
import sys
import glob
import json
import argparse
from typing import List

# Fix Windows console encoding for UTF-8 symbols
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.document_ingestion.agent import DocumentIngestionAgent, document_ingestion_node
from src.mock_data.generate_docs import generate_all_mock_scenarios


def _format_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def print_ingestion_summary(output):
    _format_banner(f"Document Ingestion Report: {output.application_id}")
    
    print(f"\n[BORROWER KYC PROFILE]")
    if output.borrower_kyc:
        print(f"  • Primary Name:        {output.borrower_kyc.primary_name}")
        print(f"  • PAN Number:          {output.borrower_kyc.pan_number or 'N/A'}")
        print(f"  • Aadhaar (Masked):    {output.borrower_kyc.aadhaar_masked or 'N/A'}")
        print(f"  • DOB / Gender:        {output.borrower_kyc.dob or 'N/A'} | {output.borrower_kyc.gender or 'N/A'}")
        print(f"  • Residential Address: {output.borrower_kyc.residential_address or 'N/A'}")
    
    print(f"\n[INCOME & EMPLOYMENT PROFILE]")
    if output.borrower_income:
        print(f"  • Employer:            {output.borrower_income.employer_name or 'N/A'}")
        print(f"  • Designation:         {output.borrower_income.designation or 'N/A'}")
        print(f"  • Monthly Gross Pay:   INR {output.borrower_income.monthly_gross_salary:,.2f}")
        print(f"  • Monthly Net Pay:     INR {output.borrower_income.monthly_net_salary:,.2f}")
        print(f"  • Form 16 Annual Gross:INR {output.borrower_income.annual_gross_income_form16:,.2f}")
        print(f"  • Average Bank Credit: INR {output.borrower_income.average_bank_salary_credit:,.2f}")
        print(f"  • Salary Slips Count:  {output.borrower_income.salary_slips_provided_count}")

    print(f"\n[BANKING & LIABILITIES]")
    if output.borrower_liabilities:
        print(f"  • Detected Monthly EMI:INR {output.borrower_liabilities.detected_monthly_emis:,.2f}")
        print(f"  • Active Loans Count:  {output.borrower_liabilities.active_loan_count_detected}")
        print(f"  • Cheque Bounces (6M): {output.borrower_liabilities.cheque_bounce_count_6m}")
    if output.bank_statement:
        print(f"  • Bank Name:           {output.bank_statement.bank_name}")
        print(f"  • Account No / IFSC:   {output.bank_statement.account_number} ({output.bank_statement.ifsc_code})")
        print(f"  • Avg Monthly Balance: INR {output.bank_statement.average_monthly_balance:,.2f}")
        print(f"  • Closing Balance:     INR {output.bank_statement.closing_balance:,.2f}")

    print(f"\n[PROPERTY PROFILE]")
    if output.property_profile:
        print(f"  • Document Title:      {output.property_profile.property_title}")
        print(f"  • Address:             {output.property_profile.property_address}")
        print(f"  • Super Built-up Area: {output.property_profile.super_builtup_area_sqft} Sq. Ft.")
        print(f"  • Consideration Value: INR {output.property_profile.purchase_or_market_value:,.2f}" if output.property_profile.purchase_or_market_value else "  • Consideration: N/A")
    else:
        print("  • No property document attached.")

    print(f"\n[CROSS-DOCUMENT RECONCILIATION]")
    print(f"  • Overall Match Score: {output.reconciliation.reconciliation_score * 100:.1f}%")
    if output.reconciliation.name_matches:
        for nm in output.reconciliation.name_matches:
            print(f"    - Name: [{nm.status}] {nm.document_1} ('{nm.name_1}') vs {nm.document_2} ('{nm.name_2}') -> Score: {nm.similarity_score*100:.0f}%")
    if output.reconciliation.salary_reconciliations:
        for sr in output.reconciliation.salary_reconciliations:
            print(f"    - Salary: [{sr.status}] {sr.salary_slip_month} Payslip (INR {sr.payslip_net_salary:,.2f}) vs Bank (INR {sr.bank_credited_salary:,.2f}) -> Diff: {sr.variance_percentage}%")
    if output.reconciliation.employer_reconciliation:
        er = output.reconciliation.employer_reconciliation
        print(f"    - Employer: [{er.status}] Payslip '{er.salary_slip_employer}' vs Form 16 '{er.form16_employer}' -> Score: {er.similarity_score*100:.0f}%")

    if output.reconciliation.contradictions:
        print(f"\n  [!] CONTRADICTIONS FLAGGED ({len(output.reconciliation.contradictions)}):")
        for c in output.reconciliation.contradictions:
            print(f"    • {c}")

    print(f"\n[CONFIDENCE & HUMAN-IN-THE-LOOP (HITL) ROUTING]")
    print(f"  • OCR Quality Score:       {output.confidence.ocr_quality_score * 100:.1f}%")
    print(f"  • Field Validation Score:  {output.confidence.field_validation_score * 100:.1f}%")
    print(f"  • Reconciliation Score:    {output.confidence.cross_reconciliation_score * 100:.1f}%")
    print(f"  • Completeness Score:      {output.confidence.completeness_score * 100:.1f}%")
    print(f"  • OVERALL CONFIDENCE:      {output.confidence.overall_confidence * 100:.1f}% [{output.confidence.confidence_level}]")
    print(f"  • Human Review Required:   {output.human_review.requires_human_review} (Priority: {output.human_review.review_priority})")
    
    if output.human_review.reasons:
        print(f"  • Review Reasons:")
        for r in output.human_review.reasons:
            print(f"    - {r}")
        print(f"  • Suggested Underwriter Actions:")
        for a in output.human_review.suggested_actions:
            print(f"    - {a}")

    print("\n" + "=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="India-Focused Mortgage Underwriting - Document Ingestion Agent CLI")
    parser.add_argument(
        "--demo",
        choices=["clean", "name-mismatch", "salary-mismatch", "missing-docs", "all"],
        default="clean",
        help="Run a built-in mock underwriting scenario"
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to folder containing PDF documents to ingest"
    )
    parser.add_argument(
        "--export-json",
        type=str,
        help="Path to save extracted structured JSON"
    )

    args = parser.parse_args()

    # Generate mock suites if needed
    scenarios = generate_all_mock_scenarios()

    scenario_map = {
        "clean": "clean_prime",
        "name-mismatch": "name_discrepancy",
        "salary-mismatch": "salary_discrepancy",
        "missing-docs": "missing_docs",
    }

    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input directory '{args.input}' not found.")
            sys.exit(1)
        files = glob.glob(os.path.join(args.input, "*.pdf")) + glob.glob(os.path.join(args.input, "*.png")) + glob.glob(os.path.join(args.input, "*.jpg"))
        if not files:
            print(f"No PDF/image documents found in '{args.input}'.")
            sys.exit(1)
        
        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=files,
            application_id="APP-CUSTOM-001"
        )
        print_ingestion_summary(output)

        if args.export_json:
            with open(args.export_json, "w", encoding="utf-8") as f:
                json.dump(output.model_dump(), f, indent=2)
            print(f"Saved structured extraction to {args.export_json}")

    elif args.demo == "all":
        for name, key in scenario_map.items():
            files = scenarios[key]
            output = DocumentIngestionAgent.process_document_bundle(
                file_paths=files,
                application_id=f"APP-DEMO-{name.upper()}"
            )
            print_ingestion_summary(output)
    else:
        key = scenario_map.get(args.demo, "clean_prime")
        files = scenarios[key]
        output = DocumentIngestionAgent.process_document_bundle(
            file_paths=files,
            application_id=f"APP-DEMO-{args.demo.upper()}"
        )
        print_ingestion_summary(output)

        if args.export_json:
            with open(args.export_json, "w", encoding="utf-8") as f:
                json.dump(output.model_dump(), f, indent=2)
            print(f"Saved structured extraction to {args.export_json}")


if __name__ == "__main__":
    main()
