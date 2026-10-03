"""
Mock Document Generator for Indian Mortgage Underwriting System.
Generates realistic Indian mortgage test document packages (PDF format) using PyMuPDF (fitz):
- Scenario 1: Clean Prime Salaried Borrower (Aarav Sharma - TCS)
- Scenario 2: Name Discrepancy Case (Priya Suresh Patel vs Priya S Patel)
- Scenario 3: Income Discrepancy Case (Vikram Malhotra - Payslip vs Bank Credit mismatch)
- Scenario 4: Missing Mandatory Documents Case (Rahul Verma - Missing Bank Statement & KYC)
"""

import os
import fitz  # PyMuPDF
from datetime import date
from typing import Dict, List, Any, Optional


def _recent_month_year(months_ago: int) -> str:
    """'June 2026'-style label for the month `months_ago` months before
    today, so the bundled payslips always pass the recency check (last 3
    months) regardless of when this generator is run."""
    today = date.today()
    month_index = today.month - 1 - months_ago  # 0-based, can go negative
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1).strftime("%B %Y")


def _create_pdf_document(output_path: str, pages_content: List[Dict[str, Any]] = None):
    """Helper to create a cleanly formatted PDF document with headings, lines, and text blocks."""
    doc = fitz.open()
    
    for p_data in pages_content:
        page = doc.new_page(width=595, height=842)  # A4 size in points
        
        # Header Box
        header_title = p_data.get("title", "")
        subtitle = p_data.get("subtitle", "")
        
        # Draw top banner
        page.draw_rect(fitz.Rect(30, 30, 565, 80), color=(0.1, 0.2, 0.4), fill=(0.93, 0.95, 0.98))
        page.insert_text((45, 55), header_title, fontsize=14, fontname="helv", color=(0.1, 0.2, 0.4))
        if subtitle:
            page.insert_text((45, 72), subtitle, fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
            
        y_pos = 105
        
        # Sections
        sections = p_data.get("sections", [])
        for sec in sections:
            sec_heading = sec.get("heading", "")
            if sec_heading:
                page.draw_line(fitz.Point(30, y_pos), fitz.Point(565, y_pos), color=(0.7, 0.7, 0.7), width=0.5)
                y_pos += 15
                page.insert_text((35, y_pos), sec_heading.upper(), fontsize=10, fontname="helv", color=(0.1, 0.3, 0.6))
                y_pos += 15
            
            items = sec.get("items", [])
            for k, v in items:
                page.insert_text((45, y_pos), f"{k}:", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
                page.insert_text((200, y_pos), str(v), fontsize=9, fontname="helv", color=(0.0, 0.0, 0.0))
                y_pos += 16
            
            tables = sec.get("table", None)
            if tables:
                headers = tables.get("headers", [])
                rows = tables.get("rows", [])
                
                # Draw table header
                page.draw_rect(fitz.Rect(40, y_pos, 555, y_pos + 18), color=(0.6, 0.6, 0.6), fill=(0.85, 0.88, 0.92))
                col_width = (555 - 40) / max(len(headers), 1)
                for c_idx, h in enumerate(headers):
                    page.insert_text((45 + c_idx * col_width, y_pos + 12), h, fontsize=8, fontname="helv", color=(0.1, 0.1, 0.1))
                y_pos += 20
                
                # Draw rows
                for r_idx, row in enumerate(rows):
                    fill_c = (0.97, 0.97, 0.97) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
                    page.draw_rect(fitz.Rect(40, y_pos, 555, y_pos + 16), color=(0.8, 0.8, 0.8), fill=fill_c)
                    for c_idx, cell in enumerate(row):
                        page.insert_text((45 + c_idx * col_width, y_pos + 11), str(cell), fontsize=8, fontname="helv", color=(0.1, 0.1, 0.1))
                    y_pos += 16
                y_pos += 10
            
            y_pos += 10
            
        # Footer
        footer_text = p_data.get("footer", "Government of India / Financial Institution Official Record")
        page.draw_line(fitz.Point(30, 800), fitz.Point(565, 800), color=(0.8, 0.8, 0.8), width=0.5)
        page.insert_text((40, 815), footer_text, fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()

def generate_all_mock_scenarios(base_dir: str = "mock_documents") -> Dict[str, List[str]]:
    """Generates all 4 test suites of mock documents."""

    scenarios = {}

    # =========================================================================
    # SCENARIO 1: Prime Salaried Borrower (Aarav Sharma - TCS)
    # =========================================================================

    s1_dir = os.path.join(base_dir, "scenario_1_clean_prime")
    os.makedirs(s1_dir, exist_ok=True)
    s1_files = []

    # 1. PAN Card
    pan_p = os.path.join(s1_dir, "pan_card_aarav_sharma.pdf")

    _create_pdf_document(
        pan_p,
        [{
            "title": "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
            "subtitle": "Permanent Account Number Card (PAN)",
            "sections": [
                {
                    "heading": "Taxpayer Information",
                    "items": [
                        ("Permanent Account Number", "ABCPS1234F"),
                        ("Name", "Aarav Sharma"),
                        ("Father's Name", "Ramesh Sharma"),
                        ("Date of Birth", "14/08/1990"),
                        ("Signature", "Aarav Sharma (Verified Digital Signature)")
                    ]
                }
            ],
            "footer": "Income Tax Department, Government of India - Computer Generated Record"
        }]
    )

    s1_files.append(pan_p)

    # 2. Aadhaar Card
    aadhaar_p = os.path.join(
        s1_dir,
        "aadhaar_card_aarav_sharma.pdf"
    )

    _create_pdf_document(
        aadhaar_p,
        [{
            "title": "UNIQUE IDENTIFICATION AUTHORITY OF INDIA (UIDAI)",
            "subtitle": "Government of India - Mera Aadhaar, Meri Pehchan",
            "sections": [
                {
                    "heading": "Identity & Residential Details",
                    "items": [
                        ("Aadhaar Number", "XXXX-XXXX-8921"),
                        ("Name", "Aarav Sharma"),
                        ("Date of Birth", "14/08/1990"),
                        ("Gender", "MALE"),
                        (
                            "Address",
                            "Flat 402, Green Valley Apartments, "
                            "Saravanampatti, Coimbatore, Tamil Nadu, PIN: 641035"
                        ),
                        ("Pincode", "641035"),
                        ("VID", "9182 3847 1928 3491")
                    ]
                }
            ],
            "footer": "Helpdesk: 1947 | help@uidai.gov.in | www.uidai.gov.in"
        }]
    )

    s1_files.append(aadhaar_p)

    # 3. Salary Slips
    for month in [_recent_month_year(2), _recent_month_year(1), _recent_month_year(0)]:

        month_fn = month.lower().replace(" ", "_")

        sal_p = os.path.join(
            s1_dir,
            f"salary_slip_{month_fn}.pdf"
        )

        _create_pdf_document(
            sal_p,
            [{
                "title": "TATA CONSULTANCY SERVICES LTD",
                "subtitle": f"Salary Slip for the month of {month}",
                "sections": [
                    {
                        "heading": "Employee Details",
                        "items": [
                            ("Employee Name", "Aarav Sharma"),
                            ("Employee ID", "TCS-893421"),
                            ("Designation", "Lead Solutions Architect"),
                            ("Pay Period", month),
                            ("Bank A/c No", "XXXXXX789123"),
                            ("PAN", "ABCPS1234F")
                        ]
                    },
                    {
                        "heading": "Earnings & Deductions Summary",
                        "items": [
                            ("Gross Salary", "INR 1,50,000.00"),
                            ("Total Deductions", "INR 25,400.00"),
                            ("Net Pay", "INR 1,24,600.00")
                        ],
                        "table": {
                            "headers": [
                                "Earnings Component",
                                "Amount (INR)",
                                "Deductions Component",
                                "Amount (INR)"
                            ],
                            "rows": [
                                [
                                    "Basic Pay",
                                    "60,000.00",
                                    "Provident Fund (PF)",
                                    "7,200.00"
                                ],
                                [
                                    "House Rent Allowance (HRA)",
                                    "30,000.00",
                                    "Professional Tax (PT)",
                                    "200.00"
                                ],
                                [
                                    "Special Allowance",
                                    "45,000.00",
                                    "Income Tax (TDS)",
                                    "18,000.00"
                                ],
                                [
                                    "Conveyance Allowance",
                                    "15,000.00",
                                    "Voluntary Deductions",
                                    "0.00"
                                ]
                            ]
                        }
                    }
                ],
                "footer": "This is a computer generated pay slip and does not require a physical signature."
            }]
        )

        s1_files.append(sal_p)

    # 4. Form 16
    f16_p = os.path.join(
        s1_dir,
        "form_16_ay_2026_27.pdf"
    )

    _create_pdf_document(
        f16_p,
        [{
            "title": "FORM NO. 16 - PART B",
            "subtitle": "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary",
            "sections": [
                {
                    "heading": "Employer and Employee Identification",
                    "items": [
                        ("Name of the Employer/Deductor", "Tata Consultancy Services Ltd"),
                        ("TAN of Deductor", "BLRT12345A"),
                        ("Name of the Employee", "Aarav Sharma"),
                        ("PAN of Employee", "ABCPS1234F"),
                        ("Assessment Year", "2026-27"),
                        ("Financial Year", "2025-26")
                    ]
                },
                {
                    "heading": "Summary of Salary & Tax Calculation",
                    "items": [
                        ("Gross Salary (Section 17(1))", "INR 18,00,000.00"),
                        ("Standard Deduction u/s 16(ia)", "INR 50,000.00"),
                        ("Total Deductions Chapter VI-A (80C, 80D)", "INR 1,50,000.00"),
                        ("Total Taxable Income", "INR 16,00,000.00"),
                        ("Total TDS Deducted", "INR 2,16,000.00")
                    ]
                }
            ],
            "footer": "Verified under Income Tax Department Guidelines | Deductor Signatory Official"
        }]
    )

    s1_files.append(f16_p)

    # 5. Bank Statement
    stmt_p = os.path.join(
        s1_dir,
        "bank_statement_6m_hdfc.pdf"
    )

    _create_pdf_document(
        stmt_p,
        [{
            "title": "HDFC BANK LIMITED - ACCOUNT STATEMENT",
            "subtitle": "Statement of Account - Retail Savings Account",
            "sections": [
                {
                    "heading": "Account Profile",
                    "items": [
                        ("Bank Name", "HDFC Bank"),
                        ("Account Holder Name", "Aarav Sharma"),
                        ("Account Number", "50100456789123"),
                        ("IFSC Code", "HDFC0001234"),
                        ("Branch", "Saravanampatti Coimbatore Branch"),
                        ("Statement Period", "01/01/2026 to 30/06/2026"),
                        ("Average Monthly Balance (AMB)", "INR 1,85,000.00"),
                        ("Closing Balance", "INR 2,40,000.00")
                    ]
                },
                {
                    "heading": "Key Transactions Summary (Last 6 Months)",
                    "table": {
                        "headers": [
                            "Date",
                            "Description / Narration",
                            "Chq/Ref No",
                            "Debit (INR)",
                            "Credit (INR)",
                            "Balance (INR)"
                        ],
                        "rows": [
                            [
                                "01/04/2026",
                                "SALARY CREDIT TCS PAYROLL",
                                "CMS00984",
                                "0.00",
                                "1,24,600.00",
                                "2,10,000.00"
                            ],
                            [
                                "05/04/2026",
                                "ACH DEBIT HDFC AUTO LOAN EMI",
                                "ACH48392",
                                "15,000.00",
                                "0.00",
                                "1,95,000.00"
                            ],
                            [
                                "01/05/2026",
                                "SALARY CREDIT TCS PAYROLL",
                                "CMS01124",
                                "0.00",
                                "1,24,600.00",
                                "2,28,000.00"
                            ],
                            [
                                "05/05/2026",
                                "ACH DEBIT HDFC AUTO LOAN EMI",
                                "ACH48392",
                                "15,000.00",
                                "0.00",
                                "2,13,000.00"
                            ],
                            [
                                "01/06/2026",
                                "SALARY CREDIT TCS PAYROLL",
                                "CMS01348",
                                "0.00",
                                "1,24,600.00",
                                "2,55,000.00"
                            ],
                            [
                                "05/06/2026",
                                "ACH DEBIT HDFC AUTO LOAN EMI",
                                "ACH48392",
                                "15,000.00",
                                "0.00",
                                "2,40,000.00"
                            ]
                        ]
                    }
                }
            ],
            "footer": "HDFC Bank Customer Support: 1800 202 6161 | Total Inward Cheque Returns: 0"
        }]
    )

    s1_files.append(stmt_p)

    # 6. Property Sale Deed
    deed_p = os.path.join(
        s1_dir,
        "property_sale_deed_coimbatore.pdf"
    )

    _create_pdf_document(
        deed_p,
        [{
            "title": "GOVERNMENT OF TAMIL NADU - DEPARTMENT OF STAMPS & REGISTRATION",
            "subtitle": "Deed of Absolute Sale for Residential Plot",
            "sections": [
                {
                    "heading": "Parties to the Agreement",
                    "items": [
                        ("Document Title", "Sale Deed"),
                        ("Registration Number", "CBE-SAR-4458/2026"),
                        ("Vendor / Developer", "Lakshmi Layouts Pvt Ltd"),
                        ("Purchaser / Buyer", "Aarav Sharma"),
                        ("Property Type", "Residential Plot")
                    ]
                },
                {
                    "heading": "Schedule Property Specifications",
                    "items": [
                        (
                            "Property Address",
                            "Plot 27, Lakshmi Nagar Layout, "
                            "Thondamuthur, Coimbatore, Tamil Nadu, PIN: 641109"
                        ),
                        ("Plot Area", "2,400.00 Sq. Ft."),
                        ("Consideration Amount", "INR 75,00,000.00"),
                        ("Stamp Duty Paid", "INR 3,75,000.00")
                    ]
                }
            ],
            "footer": "Office of the Sub-Registrar, Thondamuthur, Coimbatore | Registered & Sealed"
        }]
    )

    s1_files.append(deed_p)

    scenarios["clean_prime"] = s1_files

    # =========================================================================
    # SCENARIO 2: Name Discrepancy Case
    # =========================================================================

    s2_dir = os.path.join(
        base_dir,
        "scenario_2_name_discrepancy"
    )
    os.makedirs(s2_dir, exist_ok=True)
    s2_files = []

    # PAN
    p_pan = os.path.join(
        s2_dir,
        "pan_priya_patel.pdf"
    )

    _create_pdf_document(
        p_pan,
        [{
            "title": "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
            "subtitle": "Permanent Account Number Card (PAN)",
            "sections": [
                {
                    "heading": "Taxpayer Information",
                    "items": [
                        ("Permanent Account Number", "ABCPP5678K"),
                        ("Name", "Priya Suresh Patel"),
                        ("Father's Name", "Suresh Patel"),
                        ("Date of Birth", "22/11/1993")
                    ]
                }
            ]
        }]
    )

    s2_files.append(p_pan)

    # Aadhaar
    p_aadh = os.path.join(
        s2_dir,
        "aadhaar_priya_s_patel.pdf"
    )

    _create_pdf_document(
        p_aadh,
        [{
            "title": "UNIQUE IDENTIFICATION AUTHORITY OF INDIA",
            "subtitle": "Aadhaar Card",
            "sections": [
                {
                    "heading": "Resident Information",
                    "items": [
                        ("Aadhaar Number", "XXXX-XXXX-4512"),
                        ("Name", "Priya S. Patel"),
                        ("Date of Birth", "22/11/1993"),
                        ("Gender", "FEMALE"),
                        (
                            "Address",
                            "A-302, Green Glen Layout, Bellandur, "
                            "Bengaluru, Karnataka, PIN: 560103"
                        )
                    ]
                }
            ]
        }]
    )

    s2_files.append(p_aadh)

    # Salary Slip
    p_sal = os.path.join(
        s2_dir,
        "salary_slip_priya.pdf"
    )

    _create_pdf_document(
        p_sal,
        [{
            "title": "INFOSYS LIMITED",
            "subtitle": f"Payslip for {_recent_month_year(0)}",
            "sections": [
                {
                    "heading": "Employee Earnings",
                    "items": [
                        ("Employee Name", "Priya Patel"),
                        ("Employer Name", "Infosys Limited"),
                        ("Gross Salary", "INR 1,10,000.00"),
                        ("Total Deductions", "INR 18,000.00"),
                        ("Net Pay", "INR 92,000.00")
                    ]
                }
            ]
        }]
    )

    s2_files.append(p_sal)

    scenarios["name_discrepancy"] = s2_files

    # =========================================================================
    # SCENARIO 3: Income / Salary vs Bank Credit Discrepancy
    # =========================================================================

    s3_dir = os.path.join(
        base_dir,
        "scenario_3_salary_discrepancy"
    )
    os.makedirs(s3_dir, exist_ok=True)
    s3_files = []

    # PAN
    v_pan = os.path.join(
        s3_dir,
        "pan_vikram_malhotra.pdf"
    )

    _create_pdf_document(
        v_pan,
        [{
            "title": "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
            "subtitle": "Permanent Account Number Card",
            "sections": [
                {
                    "heading": "Taxpayer Details",
                    "items": [
                        ("Permanent Account Number", "ABCPO9912M"),
                        ("Name", "Vikram Malhotra"),
                        ("Date of Birth", "05/03/1988")
                    ]
                }
            ]
        }]
    )

    s3_files.append(v_pan)

    # Salary Slip
    v_sal = os.path.join(
        s3_dir,
        "salary_slip_vikram.pdf"
    )

    _create_pdf_document(
        v_sal,
        [{
            "title": "APEX RETAIL SOLUTIONS PVT LTD",
            "subtitle": f"Payslip for {_recent_month_year(0)}",
            "sections": [
                {
                    "heading": "Salary Computation",
                    "items": [
                        ("Employee Name", "Vikram Malhotra"),
                        ("Employer Name", "Apex Retail Solutions Pvt Ltd"),
                        ("Gross Salary", "INR 1,80,000.00"),
                        ("Total Deductions", "INR 20,000.00"),
                        ("Net Pay", "INR 1,60,000.00")
                    ]
                }
            ]
        }]
    )

    s3_files.append(v_sal)

    # Bank Statement
    v_bank = os.path.join(
        s3_dir,
        "bank_statement_vikram.pdf"
    )

    _create_pdf_document(
        v_bank,
        [{
            "title": "STATE BANK OF INDIA - ACCOUNT STATEMENT",
            "subtitle": "Savings Bank Account",
            "sections": [
                {
                    "heading": "Account Information",
                    "items": [
                        ("Account Holder Name", "Vikram Malhotra"),
                        ("Account Number", "30948572819"),
                        ("IFSC Code", "SBIN0004521"),
                        ("Average Monthly Balance", "INR 45,000.00")
                    ]
                },
                {
                    "heading": "Transactions",
                    "table": {
                        "headers": [
                            "Date",
                            "Narration",
                            "Debit (INR)",
                            "Credit (INR)"
                        ],
                        "rows": [
                            [
                                "01/06/2026",
                                "SALARY CREDIT APEX RETAIL",
                                "0.00",
                                "85,000.00"
                            ],
                            [
                                "01/05/2026",
                                "SALARY CREDIT APEX RETAIL",
                                "0.00",
                                "85,000.00"
                            ],
                            [
                                "01/04/2026",
                                "SALARY CREDIT APEX RETAIL",
                                "0.00",
                                "85,000.00"
                            ]
                        ]
                    }
                }
            ]
        }]
    )

    s3_files.append(v_bank)

    scenarios["salary_discrepancy"] = s3_files

    # =========================================================================
    # SCENARIO 4: Missing Mandatory Documents
    # =========================================================================

    s4_dir = os.path.join(
        base_dir,
        "scenario_4_missing_docs"
    )
    os.makedirs(s4_dir, exist_ok=True)
    s4_files = []

    # PAN
    r_pan = os.path.join(
        s4_dir,
        "pan_rahul_verma.pdf"
    )

    _create_pdf_document(
        r_pan,
        [{
            "title": "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
            "subtitle": "Permanent Account Number Card",
            "sections": [
                {
                    "heading": "Taxpayer Information",
                    "items": [
                        ("Permanent Account Number", "ABCPV4321R"),
                        ("Name", "Rahul Verma"),
                        ("Date of Birth", "10/10/1995")
                    ]
                }
            ]
        }]
    )

    s4_files.append(r_pan)

    # Salary Slip
    r_sal = os.path.join(
        s4_dir,
        "salary_slip_rahul.pdf"
    )

    _create_pdf_document(
        r_sal,
        [{
            "title": "WIPRO LIMITED",
            "subtitle": f"Payslip for {_recent_month_year(0)}",
            "sections": [
                {
                    "heading": "Employee Earnings",
                    "items": [
                        ("Employee Name", "Rahul Verma"),
                        ("Employer Name", "Wipro Limited"),
                        ("Gross Salary", "INR 80,000.00"),
                        ("Total Deductions", "INR 10,000.00"),
                        ("Net Pay", "INR 70,000.00")
                    ]
                }
            ]
        }]
    )

    s4_files.append(r_sal)

    scenarios["missing_docs"] = s4_files

    return scenarios


# =============================================================================
# SCENARIO 5: Photographed / scanned documents (JPG + PNG upload demo)
# =============================================================================
# Proves the JPG/PNG -> PDF conversion and OCR fallback (see
# app.document_ingestion.image_to_pdf / app.services.ocr): same borrower as
# the clean-prime scenario, but the PAN and Aadhaar are supplied as photos
# of the cards instead of text-layer PDFs.

def _load_font(size: int):
    """A real TrueType font OCRs far better than Pillow's tiny bitmap
    default. Falls back gracefully if none of these are installed."""
    from PIL import ImageFont

    for candidate in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _create_image_document(
    output_path: str,
    title: str,
    lines: List[tuple],
    width: int = 1000,
    height: int = 560,
) -> str:
    """Renders a simple card-style document (title + label/value lines) as
    a JPG or PNG - standing in for a borrower's phone photo of a physical
    document. Format is taken from `output_path`'s extension.

    Each "Label: Value" is drawn as ONE text run on its own line rather than
    two separately-positioned runs - a multi-column layout risks Tesseract
    reading the columns out of row order (it reads by block, not strictly
    top-to-bottom), which would misassign values to the wrong label.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, max(height, 110 + 50 * len(lines))), "white")
    d = ImageDraw.Draw(img)
    full_height = img.height
    d.rectangle([8, 8, width - 9, full_height - 9], outline=(60, 90, 130), width=3)

    title_font = _load_font(26)
    text_font = _load_font(24)

    d.rectangle([8, 8, width - 9, 70], fill=(30, 58, 95))
    d.text((28, 22), title, font=title_font, fill="white")

    y = 110
    for label, value in lines:
        text = f"{label}: {value}" if label else str(value)
        d.text((40, y), text, font=text_font, fill=(20, 30, 45))
        y += 50

    img.save(output_path)
    return output_path


def generate_image_demo_documents(base_dir: str = "mock_documents") -> List[str]:
    """Same borrower and loan as the clean-prime scenario, but PAN
    (PNG) and Aadhaar (JPG) are photographed/scanned images rather than
    PDFs, so a demo run visibly exercises image -> PDF conversion + OCR."""
    clean = generate_all_mock_scenarios(base_dir)["clean_prime"]
    other_pdfs = [p for p in clean if "pan_card" not in p and "aadhaar_card" not in p]

    img_dir = os.path.join(base_dir, "scenario_5_image_upload")
    os.makedirs(img_dir, exist_ok=True)

    pan_path = _create_image_document(
        os.path.join(img_dir, "pan_card_aarav_sharma_photo.png"),
        "INCOME TAX DEPARTMENT - GOVT. OF INDIA",
        [
            ("Permanent Account Number", "ABCPS1234F"),
            ("Name", "Aarav Sharma"),
            ("Father's Name", "Ramesh Sharma"),
            ("Date of Birth", "14/08/1990"),
        ],
    )

    aadhaar_path = _create_image_document(
        os.path.join(img_dir, "aadhaar_card_aarav_sharma_photo.jpg"),
        "UNIQUE IDENTIFICATION AUTHORITY OF INDIA",
        [
            ("Aadhaar Number", "XXXX-XXXX-8921"),
            ("Name", "Aarav Sharma"),
            ("Date of Birth", "14/08/1990"),
            ("Gender", "MALE"),
            ("Address", "Flat 402, Green Valley Apartments, Saravanampatti, Coimbatore"),
            ("Pincode", "641035"),
        ],
        width=1200,
    )

    return [pan_path, aadhaar_path] + other_pdfs


if __name__ == "__main__":
    generated = generate_all_mock_scenarios()
    print("Successfully generated all mock Indian mortgage document suites:")
    for sc, files in generated.items():
        print(f"  - {sc}: {len(files)} documents created in '{os.path.dirname(files[0])}'")
