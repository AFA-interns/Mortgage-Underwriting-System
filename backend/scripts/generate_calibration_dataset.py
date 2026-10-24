"""
Generate Calibration Dataset for Document Ingestion & Decision Agent.

Creates 20 realistic Indian mortgage application test bundles with PyMuPDF:
- 12 'PASS' cases (Clean Prime, High Income, PSU, Doctors, Minor initial variation)
- 8 'FAIL' cases (Name mismatch, Invalid PAN, Salary discrepancy, Math error, Expired payslips,
                 Missing bank statement, Cheque bounces, RERA failure)

Saves PDF bundles into: backend/mock_documents/calibration_dataset/
Saves case manifest into: backend/data/calibration_dataset.json
"""
import os
import json
from datetime import date
from typing import Dict, List, Any
from tests.mock_data.generate_docs import _create_pdf_document, _recent_month_year

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_documents", "calibration_dataset")
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "calibration_dataset.json")


def _generate_pan(output_path: str, name: str, pan: str, dob: str = "15/05/1988"):
    _create_pdf_document(
        output_path,
        [{
            "title": "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
            "subtitle": "Permanent Account Number Card (PAN)",
            "sections": [{
                "heading": "Taxpayer Information",
                "items": [
                    ("Permanent Account Number", pan),
                    ("Name", name),
                    ("Father's Name", "Suresh " + name.split()[-1] if len(name.split()) > 1 else "Father"),
                    ("Date of Birth", dob),
                    ("Signature", f"{name} (Verified Digital Signature)")
                ]
            }],
            "footer": "Income Tax Department, Government of India - Computer Generated Record"
        }]
    )


def _generate_aadhaar(output_path: str, name: str, aadhaar_masked: str, address: str, dob: str = "15/05/1988", gender: str = "MALE"):
    _create_pdf_document(
        output_path,
        [{
            "title": "UNIQUE IDENTIFICATION AUTHORITY OF INDIA (UIDAI)",
            "subtitle": "Government of India - Mera Aadhaar, Meri Pehchan",
            "sections": [{
                "heading": "Identity & Residential Details",
                "items": [
                    ("Aadhaar Number", aadhaar_masked),
                    ("Name", name),
                    ("Date of Birth", dob),
                    ("Gender", gender),
                    ("Address", address),
                    ("Pincode", address.split()[-1] if address.split()[-1].isdigit() else "560100"),
                    ("VID", "9182 3847 1928 3491")
                ]
            }],
            "footer": "Helpdesk: 1947 | help@uidai.gov.in | www.uidai.gov.in"
        }]
    )


def _generate_payslip(output_path: str, name: str, pan: str, employer: str, month: str,
                      gross: float, deductions: float, net: float, designation: str = "Manager"):
    _create_pdf_document(
        output_path,
        [{
            "title": employer.upper(),
            "subtitle": f"Salary Slip for the month of {month}",
            "sections": [
                {
                    "heading": "Employee Details",
                    "items": [
                        ("Employee Name", name),
                        ("Employee ID", f"EMP-{hash(name) % 100000:05d}"),
                        ("Designation", designation),
                        ("Pay Period", month),
                        ("Bank A/c No", f"50100{abs(hash(name)) % 100000000:09d}"),
                        ("PAN", pan)
                    ]
                },
                {
                    "heading": "Earnings & Deductions Summary",
                    "items": [
                        ("Gross Salary", f"INR {gross:,.2f}"),
                        ("Total Deductions", f"INR {deductions:,.2f}"),
                        ("Net Pay", f"INR {net:,.2f}")
                    ],
                    "table": {
                        "headers": ["Earnings Component", "Amount (INR)", "Deductions Component", "Amount (INR)"],
                        "rows": [
                            ["Basic Pay", f"{gross * 0.4:,.2f}", "Provident Fund (PF)", f"{deductions * 0.3:,.2f}"],
                            ["House Rent Allowance (HRA)", f"{gross * 0.2:,.2f}", "Professional Tax (PT)", "200.00"],
                            ["Special Allowance", f"{gross * 0.3:,.2f}", "Income Tax (TDS)", f"{deductions * 0.65:,.2f}"],
                            ["Conveyance", f"{gross * 0.1:,.2f}", "Other Deductions", f"{max(0.0, deductions * 0.05 - 200):,.2f}"]
                        ]
                    }
                }
            ],
            "footer": "This is a computer generated pay slip and does not require a physical signature."
        }]
    )


def _generate_bank_statement(output_path: str, name: str, employer: str, bank_name: str, ifsc: str,
                             monthly_salary: float, bounce_count: int = 0):
    account_num = f"50100{abs(hash(name)) % 100000000:09d}"
    rows = []
    # Key transactions for last 6 months
    for i in range(5, -1, -1):
        m_str = _recent_month_year(i)
        d_val = f"01/{((date.today().month - 1 - i) % 12) + 1:02d}/2026"
        bal = monthly_salary * 3.5 + (i * 15000)
        rows.append([
            d_val,
            f"SALARY CREDIT {employer.upper()[:15]} PAYROLL",
            f"CMS00{i+1}98",
            "0.00",
            f"{monthly_salary:,.2f}",
            f"{bal:,.2f}"
        ])
        rows.append([
            f"05/{((date.today().month - 1 - i) % 12) + 1:02d}/2026",
            "ACH DEBIT LOAN EMI",
            f"ACH483{i}",
            "12,000.00",
            "0.00",
            f"{bal - 12000:,.2f}"
        ])

    if bounce_count > 0:
        for b in range(bounce_count):
            rows.append([
                f"12/{b+1:02d}/2026",
                "INWARD RETURN ECS BOUNCE INSUFFICIENT FUNDS",
                f"RET99{b}",
                "500.00",
                "0.00",
                "15,200.00"
            ])

    _create_pdf_document(
        output_path,
        [{
            "title": f"{bank_name.upper()} LIMITED - ACCOUNT STATEMENT",
            "subtitle": "Statement of Account - Retail Savings Account",
            "sections": [
                {
                    "heading": "Account Profile",
                    "items": [
                        ("Bank Name", bank_name),
                        ("Account Holder Name", name),
                        ("Account Number", account_num),
                        ("IFSC Code", ifsc),
                        ("Branch", "Main Commercial Branch"),
                        ("Statement Period", "01/01/2026 to 30/06/2026"),
                        ("Average Monthly Balance (AMB)", f"INR {monthly_salary * 1.5:,.2f}"),
                        ("Inward ECS/Cheque Bounces", str(bounce_count))
                    ]
                },
                {
                    "heading": "Key Transactions Summary (Last 6 Months)",
                    "table": {
                        "headers": ["Date", "Description / Narration", "Chq/Ref No", "Debit (INR)", "Credit (INR)", "Balance (INR)"],
                        "rows": rows
                    }
                }
            ],
            "footer": f"{bank_name} Helpline: 1800 202 6161 | Total Inward Cheque Returns: {bounce_count}"
        }]
    )


def _generate_property_deed(output_path: str, owner_name: str, property_address: str,
                            locality: str, city: str, value: float, rera_id: str = "PRM/KA/RERA/1251/310/PR/200126"):
    _create_pdf_document(
        output_path,
        [{
            "title": "GOVERNMENT OF KARNATAKA - REGISTRATION & STAMPS DEPARTMENT",
            "subtitle": "Certified Deed of Absolute Sale (Conveyance)",
            "sections": [
                {
                    "heading": "Schedule A - Property Description",
                    "items": [
                        ("Document Title", "Deed of Absolute Sale"),
                        ("Property Address", property_address),
                        ("Locality", locality),
                        ("City", city),
                        ("State", "Karnataka"),
                        ("Pincode", "560100"),
                        ("Super Built-up Area", "1,250 sq.ft"),
                        ("Carpet Area", "1,050 sq.ft"),
                        ("Property Type", "Apartment"),
                        ("RERA Registration No", rera_id),
                        ("Sale Consideration", f"INR {value:,.2f}"),
                        ("Purchaser / Buyer", owner_name)
                    ]
                }
            ],
            "footer": "Sub-Registrar Office, Electronic City, Bengaluru - Certified True Copy"
        }]
    )


def generate_dataset():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)

    cases_manifest = []

    # -------------------------------------------------------------------------
    # 1. CLEAN PRIME APPLICATIONS (Expected: PASS)
    # -------------------------------------------------------------------------
    pass_profiles = [
        ("APP-CAL-001", "Aarav Sharma", "ABCPS1234F", "XXXX-XXXX-8921", "Tata Consultancy Services Ltd", 150000, 25000, 125000, "Saravanampatti, Coimbatore, TN 641035", 800, 5000000, 7500000),
        ("APP-CAL-002", "Sunita Rao", "BNKPR5678K", "XXXX-XXXX-3412", "HDFC Bank Limited", 220000, 35000, 185000, "Indiranagar, Bengaluru, KA 560038", 790, 7500000, 11000000),
        ("APP-CAL-003", "Rohan Mehra", "MEDPM9012L", "XXXX-XXXX-6789", "Apollo Hospitals Enterprise", 180000, 30000, 150000, "Jayanagar, Bengaluru, KA 560041", 765, 6000000, 9000000),
        ("APP-CAL-004", "Deepak Verma", "GOVPD3456M", "XXXX-XXXX-1234", "Bharat Heavy Electricals Ltd", 110000, 18000, 92000, "Electronic City, Bengaluru, KA 560100", 780, 4000000, 6500000),
        ("APP-CAL-005", "Pooja Nair", "INFPN7890N", "XXXX-XXXX-5678", "Infosys Limited", 95000, 15000, 80000, "Whitefield, Bengaluru, KA 560066", 755, 3500000, 5500000),
        ("APP-CAL-006", "Arjun Singhania", "FMCPA2345P", "XXXX-XXXX-9012", "Hindustan Unilever Ltd", 140000, 22000, 118000, "Koramangala, Bengaluru, KA 560034", 770, 5200000, 8000000),
        ("APP-CAL-007", "Kavita Iyer", "TELPK6789Q", "XXXX-XXXX-4567", "Bharti Airtel Limited", 125000, 20000, 105000, "HSR Layout, Bengaluru, KA 560102", 760, 4800000, 7200000),
        ("APP-CAL-008", "Manish Gupta", "ENGPM1234R", "XXXX-XXXX-7890", "Larsen & Toubro Ltd", 85000, 12000, 73000, "Hebbal, Bengaluru, KA 560024", 750, 3200000, 5000000),
        ("APP-CAL-009", "Neha Deshmukh", "AUTPN5678S", "XXXX-XXXX-2345", "Mahindra & Mahindra Ltd", 165000, 27000, 138000, "Marathahalli, Bengaluru, KA 560037", 795, 6200000, 9500000),
        ("APP-CAL-010", "Vikramaditya Bose", "WIPPV9012T", "XXXX-XXXX-6781", "Wipro Technologies", 190000, 32000, 158000, "Bellandur, Bengaluru, KA 560103", 775, 7000000, 10500000),
        # Minor acceptable initial variation (Priya Suresh Patel on PAN vs Priya S Patel on Aadhaar)
        ("APP-CAL-011", "Priya Suresh Patel", "PATPS4321B", "XXXX-XXXX-5522", "Accenture Solutions Pvt Ltd", 130000, 21000, 109000, "BTM Layout, Bengaluru, KA 560076", 765, 4500000, 7000000),
        ("APP-CAL-012", "Alok Nath Sharma", "SHMAP7788C", "XXXX-XXXX-9911", "Cognizant Technology Solutions", 115000, 19000, 96000, "Sarjapur Road, Bengaluru, KA 560035", 758, 4200000, 6800000),
    ]

    for app_id, name, pan, aadhaar_mask, emp, gross, ded, net, addr, cibil, loan, prop_val in pass_profiles:
        app_dir = os.path.join(BASE_DIR, app_id)
        os.makedirs(app_dir, exist_ok=True)
        file_paths = []

        # PAN
        pan_f = os.path.join(app_dir, "pan_card.pdf")
        _generate_pan(pan_f, name, pan)
        file_paths.append(pan_f)

        # Aadhaar (Minor initial variation for APP-CAL-011)
        aadhaar_f = os.path.join(app_dir, "aadhaar_card.pdf")
        aadhaar_name = "Priya S Patel" if app_id == "APP-CAL-011" else name
        _generate_aadhaar(aadhaar_f, aadhaar_name, aadhaar_mask, addr)
        file_paths.append(aadhaar_f)

        # Payslips (3 months recent)
        for m_idx in [2, 1, 0]:
            month_label = _recent_month_year(m_idx)
            sal_f = os.path.join(app_dir, f"salary_slip_{month_label.lower().replace(' ', '_')}.pdf")
            _generate_payslip(sal_f, name, pan, emp, month_label, gross, ded, net)
            file_paths.append(sal_f)

        # Bank Statement
        bank_f = os.path.join(app_dir, "bank_statement_6m.pdf")
        _generate_bank_statement(bank_f, name, emp, "HDFC Bank", "HDFC0001234", net, bounce_count=0)
        file_paths.append(bank_f)

        # Property Deed
        deed_f = os.path.join(app_dir, "property_deed.pdf")
        loc = addr.split(",")[0]
        _generate_property_deed(deed_f, name, f"Flat 304, Green Heights, {addr}", loc, "Bengaluru", prop_val)
        file_paths.append(deed_f)

        cases_manifest.append({
            "application_id": app_id,
            "borrower_name": name,
            "ground_truth_label": "PASS",
            "expected_decision": "APPROVE",
            "archetype": "Clean Prime Salaried",
            "cibil": cibil,
            "monthly_income": gross,
            "loan_amount": loan,
            "property_value": prop_val,
            "document_paths": file_paths,
            "flaw_description": "None (clean matching profile)" if app_id != "APP-CAL-011" else "Minor middle name initial variation"
        })

    # -------------------------------------------------------------------------
    # 2. FLAWED / FAILING APPLICATIONS (Expected: FAIL / SUSPEND)
    # -------------------------------------------------------------------------
    fail_cases = [
        # APP-CAL-013: Severe Name Discrepancy
        {
            "id": "APP-CAL-013",
            "name": "Rajesh Khanna",
            "pan": "KHAPN1122K",
            "aadhaar_name": "Suresh Pillai",
            "emp": "Tata Steel Ltd",
            "flaw": "Severe Name Discrepancy between PAN (Rajesh Khanna) and Aadhaar (Suresh Pillai)",
            "gross": 130000, "ded": 20000, "net": 110000, "bank_salary": 110000,
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": False, "skip_bank": False
        },
        # APP-CAL-014: Invalid PAN Format / Checksum Error
        {
            "id": "APP-CAL-014",
            "name": "Amit Bhatia",
            "pan": "AB99X12345",  # Invalid format
            "aadhaar_name": "Amit Bhatia",
            "emp": "Tech Mahindra Ltd",
            "flaw": "PAN format violation (invalid characters)",
            "gross": 120000, "ded": 18000, "net": 102000, "bank_salary": 102000,
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": False,
            "math_error": False, "skip_bank": False
        },
        # APP-CAL-015: Income & Bank Credit Mismatch
        {
            "id": "APP-CAL-015",
            "name": "Vikram Malhotra",
            "pan": "MALPV5566L",
            "aadhaar_name": "Vikram Malhotra",
            "emp": "Oracle India Pvt Ltd",
            "flaw": "Income Mismatch: Payslip Net is INR 1,40,000 but Bank Statement shows only INR 35,000",
            "gross": 160000, "ded": 20000, "net": 140000, "bank_salary": 35000,  # Huge mismatch
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": False, "skip_bank": False
        },
        # APP-CAL-016: Payslip Arithmetic Error
        {
            "id": "APP-CAL-016",
            "name": "Rohit Sen",
            "pan": "SENPR7788M",
            "aadhaar_name": "Rohit Sen",
            "emp": "ITC Limited",
            "flaw": "Payslip Math Inconsistency: Gross 1,20,000 - Deductions 15,000 declared as Net 1,25,000",
            "gross": 120000, "ded": 15000, "net": 125000, "bank_salary": 105000,  # Math error
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": True, "skip_bank": False
        },
        # APP-CAL-017: Stale / Expired Payslips (Violates 3-month recency)
        {
            "id": "APP-CAL-017",
            "name": "Sameer Joshi",
            "pan": "JOSPS9900N",
            "aadhaar_name": "Sameer Joshi",
            "emp": "Adani Enterprises",
            "flaw": "Payslip Recency Violation: Payslips are from 8, 9, 10 months ago",
            "gross": 100000, "ded": 15000, "net": 85000, "bank_salary": 85000,
            "months_ago": [10, 9, 8], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": False, "skip_bank": False
        },
        # APP-CAL-018: Missing Mandatory Bank Statement
        {
            "id": "APP-CAL-018",
            "name": "Rahul Verma",
            "pan": "VERPR3344P",
            "aadhaar_name": "Rahul Verma",
            "emp": "Bajaj Finserv",
            "flaw": "Missing Mandatory Document: Bank Statement completely omitted",
            "gross": 90000, "ded": 12000, "net": 78000, "bank_salary": 78000,
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": False, "skip_bank": True
        },
        # APP-CAL-019: Severe Inward Cheque/ECS Bounces
        {
            "id": "APP-CAL-019",
            "name": "Sanjay Kapoor",
            "pan": "KAPPS6677Q",
            "aadhaar_name": "Sanjay Kapoor",
            "emp": "Kotak Securities",
            "flaw": "Banking Default Behavior: 4 inward ECS bounces detected in 6 months",
            "gross": 145000, "ded": 22000, "net": 123000, "bank_salary": 123000,
            "months_ago": [2, 1, 0], "bounces": 4, "rera": "PRM/KA/RERA/1251/310/PR/200126", "pan_valid": True,
            "math_error": False, "skip_bank": False
        },
        # APP-CAL-020: Unregistered RERA Under-Construction Project
        {
            "id": "APP-CAL-020",
            "name": "Tarun Roy",
            "pan": "ROYPT8899R",
            "aadhaar_name": "Tarun Roy",
            "emp": "Reliance Industries",
            "flaw": "Compliance Violation: Under-construction property has unverified/missing RERA registration",
            "gross": 170000, "ded": 25000, "net": 145000, "bank_salary": 145000,
            "months_ago": [2, 1, 0], "bounces": 0, "rera": "NOT_REGISTERED", "pan_valid": True,
            "math_error": False, "skip_bank": False
        },
    ]

    for fcase in fail_cases:
        app_id = fcase["id"]
        app_dir = os.path.join(BASE_DIR, app_id)
        os.makedirs(app_dir, exist_ok=True)
        file_paths = []

        # PAN
        pan_f = os.path.join(app_dir, "pan_card.pdf")
        _generate_pan(pan_f, fcase["name"], fcase["pan"])
        file_paths.append(pan_f)

        # Aadhaar
        aadhaar_f = os.path.join(app_dir, "aadhaar_card.pdf")
        _generate_aadhaar(aadhaar_f, fcase["aadhaar_name"], "XXXX-XXXX-9999", "MG Road, Bengaluru, KA 560001")
        file_paths.append(aadhaar_f)

        # Payslips
        for m_idx in fcase["months_ago"]:
            month_label = _recent_month_year(m_idx)
            sal_f = os.path.join(app_dir, f"salary_slip_{month_label.lower().replace(' ', '_')}.pdf")
            _generate_payslip(sal_f, fcase["name"], fcase["pan"], fcase["emp"],
                              month_label, fcase["gross"], fcase["ded"], fcase["net"])
            file_paths.append(sal_f)

        # Bank Statement (unless omitted)
        if not fcase["skip_bank"]:
            bank_f = os.path.join(app_dir, "bank_statement_6m.pdf")
            _generate_bank_statement(bank_f, fcase["name"], fcase["emp"], "ICICI Bank", "ICIC0002233",
                                     fcase["bank_salary"], bounce_count=fcase["bounces"])
            file_paths.append(bank_f)

        # Property Deed
        deed_f = os.path.join(app_dir, "property_deed.pdf")
        _generate_property_deed(deed_f, fcase["name"], "Flat 502, Skyline Apartments, MG Road, Bengaluru",
                                "MG Road", "Bengaluru", 8000000, rera_id=fcase["rera"])
        file_paths.append(deed_f)

        cases_manifest.append({
            "application_id": app_id,
            "borrower_name": fcase["name"],
            "ground_truth_label": "FAIL",
            "expected_decision": "SUSPEND",
            "archetype": "Flawed Application",
            "cibil": 680,
            "monthly_income": fcase["gross"],
            "loan_amount": 4500000,
            "property_value": 7500000,
            "document_paths": file_paths,
            "flaw_description": fcase["flaw"]
        })

    with open(MANIFEST_PATH, "w", encoding="utf-8") as out:
        json.dump(cases_manifest, out, indent=2)

    print(f"Successfully generated {len(cases_manifest)} application packages.")
    print(f"Document bundles directory: {BASE_DIR}")
    print(f"Manifest saved to: {MANIFEST_PATH}")


if __name__ == "__main__":
    generate_dataset()
