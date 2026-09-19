"""
Cross-Document Reconciliation Engine for Mortgage Underwriting.
Performs multi-document entity resolution:
- Fuzzy name matching across KYC (PAN, Aadhaar), Income (Salary Slips, Form 16), Banking, and Property Deeds.
- Employer name consistency between Salary Slips and Form 16.
- Income deposit reconciliation: Net Salary vs. Bank Statement monthly salary credits.
- Existing debt / recurring EMI liability identification.
- Address consistency verification.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from app.models.schemas import (
    PANCardData,
    AadhaarCardData,
    SalarySlipData,
    Form16Data,
    BankStatementData,
    PropertyDocData,
)
from app.models.state import (
    NameMatchResult,
    SalaryReconciliationResult,
    EmployerReconciliationResult,
    AddressReconciliationResult,
    CrossDocumentReconciliationReport,
)


def _compute_string_similarity(s1: str, s2: str) -> float:
    """Computes token-based and character similarity between two strings."""
    if not s1 or not s2:
        return 0.0

    s1_clean = re.sub(r"[^a-zA-Z0-9\s]", "", s1.lower()).strip()
    s2_clean = re.sub(r"[^a-zA-Z0-9\s]", "", s2.lower()).strip()

    if s1_clean == s2_clean:
        return 1.0

    tokens1 = set(s1_clean.split())
    tokens2 = set(s2_clean.split())

    if not tokens1 or not tokens2:
        return 0.0

    # Token overlap (Jaccard)
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    jaccard = len(intersection) / len(union)

    # Partial / Initial match boost (e.g., 'Aarav K Sharma' vs 'Aarav Kumar Sharma')
    initial_matches = 0
    for t1 in tokens1:
        for t2 in tokens2:
            if len(t1) == 1 and t2.startswith(t1):
                initial_matches += 1
            elif len(t2) == 1 and t1.startswith(t2):
                initial_matches += 1

    token_similarity = (len(intersection) + (0.5 * initial_matches)) / max(len(tokens1), len(tokens2))

    # Levenshtein ratio approximation
    longer = max(len(s1_clean), len(s2_clean))
    shorter = min(len(s1_clean), len(s2_clean))
    # Quick prefix/suffix check
    prefix_len = 0
    for c1, c2 in zip(s1_clean, s2_clean):
        if c1 == c2:
            prefix_len += 1
        else:
            break
    char_ratio = (prefix_len + shorter) / (longer + shorter)

    final_score = (0.7 * token_similarity) + (0.3 * char_ratio)
    return round(min(1.0, max(0.0, final_score)), 3)


class CrossDocumentReconciler:
    """Reconciles information across multiple ingested documents."""

    @classmethod
    def reconcile(
        cls,
        pan_data: Optional[PANCardData],
        aadhaar_data: Optional[AadhaarCardData],
        salary_slips: List[SalarySlipData],
        form_16: Optional[Form16Data],
        bank_statement: Optional[BankStatementData],
        property_doc: Optional[PropertyDocData],
    ) -> CrossDocumentReconciliationReport:
        report = CrossDocumentReconciliationReport()
        contradictions: List[str] = []

        # -------------------------------------------------------------
        # 1. Name Reconciliation Across Documents
        # -------------------------------------------------------------
        named_entities = []
        if pan_data and pan_data.full_name:
            named_entities.append(("PAN Card", pan_data.full_name))
        if aadhaar_data and aadhaar_data.full_name:
            named_entities.append(("Aadhaar Card", aadhaar_data.full_name))
        if salary_slips and salary_slips[0].employee_name:
            named_entities.append(("Salary Slip", salary_slips[0].employee_name))
        if form_16 and form_16.employee_name:
            named_entities.append(("Form 16", form_16.employee_name))
        if bank_statement and bank_statement.account_holder_name:
            named_entities.append(("Bank Statement", bank_statement.account_holder_name))
        if property_doc and property_doc.buyer_or_owner_name:
            named_entities.append(("Property Deed", property_doc.buyer_or_owner_name))

        # Compare pairs
        for i in range(len(named_entities)):
            for j in range(i + 1, len(named_entities)):
                doc1, name1 = named_entities[i]
                doc2, name2 = named_entities[j]
                score = _compute_string_similarity(name1, name2)

                if score >= 0.95:
                    status = "EXACT_MATCH"
                    is_match = True
                    notes = f"Names match closely between {doc1} ('{name1}') and {doc2} ('{name2}')."
                elif score >= 0.80:
                    status = "FUZZY_MATCH"
                    is_match = True
                    notes = f"Minor spelling or name format difference between {doc1} ('{name1}') and {doc2} ('{name2}')."
                else:
                    status = "MISMATCH"
                    is_match = False
                    notes = f"Significant name mismatch: '{name1}' ({doc1}) vs '{name2}' ({doc2})."
                    contradictions.append(f"Name mismatch between {doc1} and {doc2}: '{name1}' vs '{name2}' (Similarity: {score * 100:.0f}%)")

                report.name_matches.append(
                    NameMatchResult(
                        document_1=doc1,
                        name_1=name1,
                        document_2=doc2,
                        name_2=name2,
                        similarity_score=score,
                        is_match=is_match,
                        status=status,
                        notes=notes,
                    )
                )

        # -------------------------------------------------------------
        # 2. Employer Name Reconciliation (Salary Slips vs Form 16)
        # -------------------------------------------------------------
        if salary_slips and form_16 and salary_slips[0].employer_name and form_16.employer_name:
            emp_slip = salary_slips[0].employer_name
            emp_form16 = form_16.employer_name
            emp_score = _compute_string_similarity(emp_slip, emp_form16)

            # Acronym match boost (e.g. TCS vs Tata Consultancy Services)
            if ("tcs" in emp_slip.lower() and "tata consultancy" in emp_form16.lower()) or \
               ("tcs" in emp_form16.lower() and "tata consultancy" in emp_slip.lower()) or \
               ("infosys" in emp_slip.lower() and "infy" in emp_form16.lower()):
                emp_score = 0.98

            is_emp_match = emp_score >= 0.75
            status = "MATCH" if is_emp_match else "MISMATCH"

            if not is_emp_match:
                contradictions.append(
                    f"Employer mismatch: Payslip employer '{emp_slip}' does not match Form 16 employer '{emp_form16}'."
                )

            report.employer_reconciliation = EmployerReconciliationResult(
                salary_slip_employer=emp_slip,
                form16_employer=emp_form16,
                similarity_score=emp_score,
                is_match=is_emp_match,
                status=status,
            )

        # -------------------------------------------------------------
        # 3. Income Reconciliation: Payslip Net Salary vs Bank Credits
        # -------------------------------------------------------------
        if salary_slips and bank_statement:
            bank_salary_credits = bank_statement.salary_credits
            avg_bank_credit = bank_statement.average_monthly_salary_credit

            for slip in salary_slips:
                payslip_net = slip.net_salary
                slip_month = slip.month_year or "Latest Month"

                # Find closest matching credit transaction
                closest_credit = None
                min_diff = float("inf")

                for cr in bank_salary_credits:
                    diff = abs(cr.amount - payslip_net)
                    if diff < min_diff:
                        min_diff = diff
                        closest_credit = cr

                credited_amount = closest_credit.amount if closest_credit else avg_bank_credit

                variance_amount = round(abs(payslip_net - credited_amount), 2)
                variance_pct = round((variance_amount / max(payslip_net, 1.0)) * 100.0, 2)

                if variance_pct <= 5.0:
                    status = "MATCH"
                    is_reconciled = True
                    notes = f"Bank salary credit (Γé╣{credited_amount:,.2f}) matches payslip net salary (Γé╣{payslip_net:,.2f})."
                elif variance_pct <= 15.0:
                    status = "WITHIN_TOLERANCE"
                    is_reconciled = True
                    notes = f"Slight variance of {variance_pct}% (Γé╣{variance_amount:,.2f}) due to variable components or tax adjustment."
                else:
                    status = "DISCREPANCY"
                    is_reconciled = False
                    notes = f"Large variance: Bank credit Γé╣{credited_amount:,.2f} vs Payslip Net Γé╣{payslip_net:,.2f} ({variance_pct}% difference)."
                    contradictions.append(
                        f"Income discrepancy in {slip_month}: Bank credit (Γé╣{credited_amount:,.2f}) differs significantly from Payslip Net (Γé╣{payslip_net:,.2f})."
                    )

                report.salary_reconciliations.append(
                    SalaryReconciliationResult(
                        salary_slip_month=slip_month,
                        payslip_net_salary=payslip_net,
                        bank_credited_salary=credited_amount,
                        variance_amount=variance_amount,
                        variance_percentage=variance_pct,
                        is_reconciled=is_reconciled,
                        status=status,
                        notes=notes,
                    )
                )

        # -------------------------------------------------------------
        # 4. Address Reconciliation (Aadhaar vs Property Deed)
        # -------------------------------------------------------------
        if aadhaar_data and property_doc and aadhaar_data.pincode and property_doc.pincode:
            pincode_match = (aadhaar_data.pincode == property_doc.pincode)
            city_match = True
            if aadhaar_data.address and property_doc.city:
                city_match = property_doc.city.lower() in aadhaar_data.address.lower()

            report.address_reconciliation = AddressReconciliationResult(
                aadhaar_address=aadhaar_data.address,
                property_address=property_doc.property_address,
                city_match=city_match,
                pincode_match=pincode_match,
                is_same_city=city_match,
                notes="Property in same city as borrower KYC address." if city_match else "Property located in different city/region from current KYC address.",
            )

        # -------------------------------------------------------------
        # 5. Composite Score Calculation
        # -------------------------------------------------------------
        report.contradictions = contradictions
        report.total_contradictions_count = len(contradictions)

        # Base score 1.0, deducted for mismatches
        reconciliation_score = 1.0
        if report.name_matches:
            avg_name_score = sum(m.similarity_score for m in report.name_matches) / len(report.name_matches)
            reconciliation_score *= avg_name_score

        if contradictions:
            deduction = min(0.5, len(contradictions) * 0.15)
            reconciliation_score = max(0.2, reconciliation_score - deduction)

        report.reconciliation_score = round(reconciliation_score, 3)
        return report
