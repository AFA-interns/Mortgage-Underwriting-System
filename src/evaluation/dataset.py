"""
Benchmark Evaluation Dataset and Ground Truth Definitions for Document Ingestion Agent.
Includes 40 labeled Indian home loan application cases:
- 15 Clean Prime Salaried cases (expected: PROCEED)
- 8 Name Discrepancy cases (spelling variants: PROCEED after re-match; genuine conflicts: REQUEST_RESUBMISSION)
- 7 Income / Banking Variance cases (within variance limit: PROCEED_CONSERVATIVE; beyond: REQUEST_RESUBMISSION)
- 6 Missing Mandatory Document cases (expected: REQUEST_RESUBMISSION)
- 4 Low-Quality Scan & Noise cases (recoverable: PROCEED; unrecoverable: REQUEST_RESUBMISSION)
"""

from typing import List, Dict, Any


def get_benchmark_dataset() -> List[Dict[str, Any]]:
    """Returns the benchmark labeled evaluation dataset with expected automated outcomes."""
    cases = []

    # 1. 15 Clean Prime Salaried Cases -> Expected: PROCEED
    prime_names = [
        ("Aarav Sharma", "ABCPS1234F", "Tata Consultancy Services Ltd", 150000.0, 124600.0),
        ("Aditya Verma", "ABCPV5678G", "Infosys Limited", 135000.0, 112000.0),
        ("Rohan Kulkarni", "ABCPK9123H", "Wipro Limited", 160000.0, 131500.0),
        ("Neha Gupta", "ABCPG3456J", "HCL Technologies Ltd", 125000.0, 104000.0),
        ("Siddharth Rao", "ABCPR7890K", "Cognizant Technology Solutions", 175000.0, 142000.0),
        ("Kavya Nair", "ABCPN2345L", "Accenture Solutions Pvt Ltd", 140000.0, 116500.0),
        ("Ananya Iyer", "ABCPI6789M", "LTIMindtree Limited", 155000.0, 128000.0),
        ("Manish Joshi", "ABCPJ1234N", "Tech Mahindra Limited", 130000.0, 108000.0),
        ("Deepak Reddy", "ABCPR5678P", "Oracle India Pvt Ltd", 210000.0, 168000.0),
        ("Pooja Hegde", "ABCPH9012Q", "Cisco Systems India Pvt Ltd", 225000.0, 179000.0),
        ("Varun Saxena", "ABCPS3456R", "Microsoft India R&D Pvt Ltd", 280000.0, 218000.0),
        ("Sneha Deshmukh", "ABCPD7890S", "Amazon Development Centre India", 260000.0, 204000.0),
        ("Rajesh Pillai", "ABCPP2345T", "Google India Pvt Ltd", 310000.0, 241000.0),
        ("Divya Menon", "ABCPM6789U", "Flipkart Internet Pvt Ltd", 190000.0, 152000.0),
        ("Kunal Ghosh", "ABCPG1234V", "Swiggy (Bundl Technologies)", 170000.0, 137000.0),
    ]

    for idx, (name, pan, emp, gross, net) in enumerate(prime_names):
        cases.append({
            "case_id": f"BENCH-PRIME-{idx+1:03d}",
            "category": "CLEAN_PRIME",
            "borrower_name": name,
            "pan_number": pan,
            "employer_name": emp,
            "gross_salary": gross,
            "net_salary": net,
            "has_contradiction": False,
            "expected_automated_outcome": "PROCEED",
            "expected_hitl": False,  # Legacy field
            "expected_confidence_min": 0.90,
            "doc_types_included": ["PAN_CARD", "AADHAAR_CARD", "SALARY_SLIP", "FORM_16", "BANK_STATEMENT", "PROPERTY_DEED"],
        })

    # 2. 8 Name Discrepancy Cases
    # Minor spelling variants (4 cases) -> PROCEED after re-match
    # Genuine conflicts (4 cases) -> REQUEST_RESUBMISSION
    name_cases = [
        ("Priya Suresh Patel", "Priya S. Patel", "Priya Patel", "ABCPP5678K", "PROCEED"),          # minor initial variant
        ("Suresh Kumar Menon", "Suresh K. Menon", "Suresh Menon", "ABCPM1234A", "PROCEED"),         # minor initial variant
        ("Vikramaditya Singh", "Vikram Singh", "Vikramaditya Singh", "ABCPS5678B", "PROCEED"),      # abbreviation variant
        ("Lakshmi Narayanan", "Laxmi Narayanan", "Lakshmi N.", "ABCPL9012C", "PROCEED"),            # phonetic transliteration variant
        ("Mohammed Rizwan Khan", "Md. Rizwan Khan", "Rizwan Ahmed", "ABCPK3456D", "REQUEST_RESUBMISSION"),  # surname conflict
        ("Harshvardhan Rathi", "Harsh V. Rathi", "Harshvardhan Sharma", "ABCPR7890E", "REQUEST_RESUBMISSION"), # surname conflict
        ("Shweta Ananthakrishnan", "Shweta A.", "Shweta Mukherjee", "ABCPA2345F", "REQUEST_RESUBMISSION"),     # surname conflict
        ("Gurpreet Singh Sodhi", "Gurpreet S. Sodhi", "Gurpreet Kaur", "ABCPS6789G", "REQUEST_RESUBMISSION"),  # gendered surname conflict
    ]
    for idx, (n_pan, n_aadh, n_sal, pan, exp_outcome) in enumerate(name_cases):
        cases.append({
            "case_id": f"BENCH-NAME-{idx+1:03d}",
            "category": "NAME_DISCREPANCY",
            "pan_name": n_pan,
            "aadhaar_name": n_aadh,
            "salary_name": n_sal,
            "pan_number": pan,
            "has_contradiction": True,
            "expected_automated_outcome": exp_outcome,
            "expected_hitl": True,
            "expected_confidence_max": 0.84,
            "doc_types_included": ["PAN_CARD", "AADHAAR_CARD", "SALARY_SLIP"],
        })

    # 3. 7 Income / Banking Discrepancy Cases
    # Within variance limit (e.g. up to 10-15%) -> PROCEED_CONSERVATIVE
    # Beyond variance limit (> 30% gap) -> REQUEST_RESUBMISSION
    income_cases = [
        ("Vikram Malhotra", 180000.0, 160000.0, 148000.0, "Apex Retail Solutions", "PROCEED_CONSERVATIVE"), # ~7.5% gap (within limit)
        ("Rahul Sengupta", 140000.0, 115000.0, 105000.0, "Zenith Logistics", "PROCEED_CONSERVATIVE"),       # ~8.7% gap (within limit)
        ("Amitabh Sen", 200000.0, 165000.0, 150000.0, "Apex Builders Pvt Ltd", "PROCEED_CONSERVATIVE"),     # ~9.0% gap (within limit)
        ("Karthik Sundaram", 110000.0, 92000.0, 45000.0, "Matrix Media", "REQUEST_RESUBMISSION"),            # 51% gap (beyond limit)
        ("Naveen Reddy", 150000.0, 125000.0, 70000.0, "Venture Enterprises", "REQUEST_RESUBMISSION"),        # 44% gap (beyond limit)
        ("Anuradha Roy", 130000.0, 108000.0, 50000.0, "Delta Manufacturing", "REQUEST_RESUBMISSION"),       # 53% gap (beyond limit)
        ("Praveen Chawla", 165000.0, 138000.0, 80000.0, "Pinnacle Consultancy", "REQUEST_RESUBMISSION"),    # 42% gap (beyond limit)
    ]
    for idx, (name, gross, net, bank_cr, emp, exp_outcome) in enumerate(income_cases):
        cases.append({
            "case_id": f"BENCH-INCOME-{idx+1:03d}",
            "category": "INCOME_DISCREPANCY",
            "borrower_name": name,
            "gross_salary": gross,
            "net_salary": net,
            "bank_credited_salary": bank_cr,
            "employer_name": emp,
            "has_contradiction": True,
            "expected_automated_outcome": exp_outcome,
            "expected_hitl": True,
            "doc_types_included": ["PAN_CARD", "SALARY_SLIP", "BANK_STATEMENT"],
        })

    # 4. 6 Missing Mandatory Document Cases -> Expected: REQUEST_RESUBMISSION
    missing_cases = [
        ("Rahul Verma", ["PAN_CARD", "SALARY_SLIP"], ["Aadhaar Card", "Bank Statement", "Property Deed"]),
        ("Sunil Kumar", ["AADHAAR_CARD", "BANK_STATEMENT"], ["PAN Card", "Income Proof", "Property Deed"]),
        ("Pooja Nair", ["PAN_CARD", "AADHAAR_CARD"], ["Income Proof", "Bank Statement", "Property Deed"]),
        ("Ashish Mehta", ["SALARY_SLIP", "BANK_STATEMENT"], ["PAN Card", "Aadhaar Card", "Property Deed"]),
        ("Geeta Rao", ["PAN_CARD", "AADHAAR_CARD", "SALARY_SLIP"], ["Bank Statement", "Property Deed"]),
        ("Sanjay Bhat", ["PAN_CARD", "BANK_STATEMENT", "PROPERTY_DEED"], ["Aadhaar Card", "Salary Slips / Income Proof"]),
    ]
    for idx, (name, provided, missing) in enumerate(missing_cases):
        cases.append({
            "case_id": f"BENCH-MISSING-{idx+1:03d}",
            "category": "MISSING_DOCUMENTS",
            "borrower_name": name,
            "provided_docs": provided,
            "missing_docs": missing,
            "has_contradiction": False,
            "expected_automated_outcome": "REQUEST_RESUBMISSION",
            "expected_hitl": True,
            "doc_types_included": provided,
        })

    # 5. 4 Low-Quality Scan & Noise Cases
    # Recoverable (noise_cer < 0.07) -> PROCEED
    # Otherwise -> REQUEST_RESUBMISSION
    scan_cases = [
        ("Tarun Bajaj", "ABCPB1122C", "Skewed and noisy PAN image", 0.08, 0.86, "REQUEST_RESUBMISSION"),
        ("Meera Saxena", "XXXX-XXXX-9911", "Low-contrast Aadhaar scan", 0.06, 0.88, "PROCEED"),
        ("Girish Pandey", "1100045612", "Faded thermal printed bank statement", 0.09, 0.82, "REQUEST_RESUBMISSION"),
        ("Rekha Swaminathan", "BNG-2026-99", "Watermarked property deed scan", 0.05, 0.89, "PROCEED"),
    ]
    for idx, (name, id_val, note, noise_cer, expected_f1, exp_outcome) in enumerate(scan_cases):
        cases.append({
            "case_id": f"BENCH-SCAN-{idx+1:03d}",
            "category": "LOW_QUALITY_SCAN",
            "borrower_name": name,
            "id_value": id_val,
            "noise_level": note,
            "simulated_cer": noise_cer,
            "expected_token_f1": expected_f1,
            "has_contradiction": False,
            "expected_automated_outcome": exp_outcome,
            "expected_hitl": False if noise_cer < 0.07 else True,
            "doc_types_included": ["PAN_CARD", "AADHAAR_CARD", "SALARY_SLIP"],
        })

    return cases
