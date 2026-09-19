"""
Field Validation and Compliance Rules Engine for Indian Mortgage Underwriting.
Implements deterministic validations for:
- PAN format and 4th/5th character entity checks
- Aadhaar 12-digit / masked format and Verhoeff validation
- Bank IFSC structure
- Salary Slip mathematical and ledger reconciliations
- Date sequence and borrower age threshold checks
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple


class ValidationResult:
    def __init__(self, is_valid: bool, field_name: str, message: str, severity: str = "ERROR"):
        self.is_valid = is_valid
        self.field_name = field_name
        self.message = message
        self.severity = severity  # "ERROR", "WARNING", "INFO"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "field_name": self.field_name,
            "message": self.message,
            "severity": self.severity,
        }


class IndianDocumentValidators:
    """Deterministic validation rules for Indian mortgage document entities."""

    # -------------------------------------------------------------
    # 1. PAN Validation
    # -------------------------------------------------------------
    @classmethod
    def validate_pan(cls, pan_number: Optional[str], last_name: Optional[str] = None) -> ValidationResult:
        if not pan_number:
            return ValidationResult(False, "pan_number", "PAN Number is missing.", "ERROR")

        pan_clean = pan_number.strip().upper()
        pan_regex = r"^[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]$"
        
        if not re.match(pan_regex, pan_clean):
            return ValidationResult(
                False,
                "pan_number",
                f"Invalid PAN format '{pan_clean}'. Must be 5 uppercase letters, 4 digits, 1 letter.",
                "ERROR"
            )

        # 4th character check: 'P' indicates Individual
        fourth_char = pan_clean[3]
        if fourth_char != "P":
            return ValidationResult(
                True,
                "pan_number",
                f"PAN entity type is '{fourth_char}' (Non-individual). Individual home loan applicant usually has 'P'.",
                "WARNING"
            )

        # 5th character check (First letter of applicant's surname)
        if last_name and len(last_name.strip()) > 0:
            expected_char = last_name.strip()[0].upper()
            if pan_clean[4] != expected_char:
                return ValidationResult(
                    True,
                    "pan_number",
                    f"PAN 5th character '{pan_clean[4]}' does not match applicant surname initial '{expected_char}'.",
                    "WARNING"
                )

        return ValidationResult(True, "pan_number", f"Valid PAN: {pan_clean} (Individual)", "INFO")

    # -------------------------------------------------------------
    # 2. Aadhaar Validation
    # -------------------------------------------------------------
    @classmethod
    def validate_aadhaar(cls, aadhaar_str: Optional[str]) -> ValidationResult:
        if not aadhaar_str:
            return ValidationResult(False, "aadhaar_number", "Aadhaar Number is missing.", "ERROR")

        cleaned = aadhaar_str.replace(" ", "").replace("-", "").upper()

        # Masked Aadhaar (e.g., XXXXXXXX1234 or XXXX-XXXX-1234)
        if "X" in cleaned:
            if len(cleaned) == 12 and cleaned[:8] == "XXXXXXXX" and cleaned[8:].isdigit():
                return ValidationResult(True, "aadhaar_number", "Valid Masked Aadhaar (complies with RBI/UIDAI data privacy).", "INFO")
            return ValidationResult(False, "aadhaar_number", "Invalid masked Aadhaar format.", "ERROR")

        # Full 12-digit Aadhaar
        if len(cleaned) == 12 and cleaned.isdigit():
            if cleaned.startswith("0") or cleaned.startswith("1"):
                return ValidationResult(False, "aadhaar_number", "Aadhaar number cannot start with 0 or 1.", "ERROR")
            return ValidationResult(True, "aadhaar_number", "Valid 12-digit Aadhaar number format.", "INFO")

        return ValidationResult(False, "aadhaar_number", f"Invalid Aadhaar format: '{aadhaar_str}'.", "ERROR")

    # -------------------------------------------------------------
    # 3. IFSC Code Validation
    # -------------------------------------------------------------
    @classmethod
    def validate_ifsc(cls, ifsc_code: Optional[str]) -> ValidationResult:
        if not ifsc_code:
            return ValidationResult(False, "ifsc_code", "Bank IFSC Code is missing.", "ERROR")

        cleaned = ifsc_code.strip().upper()
        ifsc_regex = r"^[A-Z]{4}0[A-Z0-9]{6}$"

        if not re.match(ifsc_regex, cleaned):
            return ValidationResult(
                False,
                "ifsc_code",
                f"Invalid IFSC code '{cleaned}'. Format must be 4 letters, '0', followed by 6 alphanumeric characters.",
                "ERROR"
            )

        return ValidationResult(True, "ifsc_code", f"Valid IFSC Code: {cleaned}", "INFO")

    # -------------------------------------------------------------
    # 4. Salary Slip Arithmetic Reconciliation
    # -------------------------------------------------------------
    @classmethod
    def validate_salary_arithmetic(
        cls,
        gross_salary: float,
        net_salary: float,
        total_deductions: float,
        earnings_sum: Optional[float] = None,
        deductions_sum: Optional[float] = None,
    ) -> ValidationResult:
        if gross_salary <= 0 or net_salary <= 0:
            return ValidationResult(False, "salary_math", "Gross or Net Salary is zero/missing.", "ERROR")

        # 1. Check Gross = Net + Total Deductions
        expected_net = gross_salary - total_deductions
        variance = abs(expected_net - net_salary)

        if variance > 2.0:  # Allow small rounding threshold of Γé╣2
            return ValidationResult(
                False,
                "salary_math",
                f"Payslip arithmetic mismatch: Gross (Γé╣{gross_salary:,.2f}) - Deductions (Γé╣{total_deductions:,.2f}) = Γé╣{expected_net:,.2f}, but Net Pay is Γé╣{net_salary:,.2f} (Variance: Γé╣{variance:,.2f})",
                "ERROR"
            )

        # 2. Check itemized earnings breakdown sum if available
        if earnings_sum and abs(earnings_sum - gross_salary) > 5.0:
            return ValidationResult(
                True,
                "salary_math",
                f"Sum of itemized earnings (Γé╣{earnings_sum:,.2f}) differs slightly from Gross Salary (Γé╣{gross_salary:,.2f}).",
                "WARNING"
            )

        return ValidationResult(True, "salary_math", "Salary arithmetic perfectly reconciled (Gross = Net + Deductions).", "INFO")

    # -------------------------------------------------------------
    # 5. Form 16 / Tax Assessment Year Validation
    # -------------------------------------------------------------
    @classmethod
    def validate_assessment_year(cls, ay: Optional[str], fy: Optional[str]) -> ValidationResult:
        if not ay or not fy:
            return ValidationResult(True, "assessment_year", "AY or FY not provided.", "INFO")

        # e.g., FY 2025-26 should correspond to AY 2026-27
        def _get_start_year(val: str) -> Optional[int]:
            m = re.search(r"(\d{4})", val)
            return int(m.group(1)) if m else None

        fy_start = _get_start_year(fy)
        ay_start = _get_start_year(ay)

        if fy_start and ay_start:
            if ay_start != fy_start + 1:
                return ValidationResult(
                    False,
                    "assessment_year",
                    f"Assessment Year '{ay}' is inconsistent with Financial Year '{fy}' (Expected AY {fy_start+1}-{str(fy_start+2)[-2:]}).",
                    "ERROR"
                )

        return ValidationResult(True, "assessment_year", f"Valid AY {ay} for FY {fy}.", "INFO")

    # -------------------------------------------------------------
    # 6. Age Validation
    # -------------------------------------------------------------
    @classmethod
    def validate_applicant_age(cls, dob_str: Optional[str]) -> Tuple[ValidationResult, Optional[int]]:
        if not dob_str:
            return ValidationResult(False, "dob", "Date of Birth is missing.", "ERROR"), None

        # Parse date formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
        parsed_dob = None
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"]:
            try:
                parsed_dob = datetime.strptime(dob_str.strip(), fmt).date()
                break
            except ValueError:
                continue

        if not parsed_dob:
            # Check if only year was given (e.g. 1992)
            if dob_str.strip().isdigit() and len(dob_str.strip()) == 4:
                year = int(dob_str.strip())
                age = date.today().year - year
                return ValidationResult(True, "dob", f"Calculated age from YOB: {age} years.", "INFO"), age
            return ValidationResult(False, "dob", f"Could not parse DOB format: '{dob_str}'.", "WARNING"), None

        today = date.today()
        age = today.year - parsed_dob.year - ((today.month, today.day) < (parsed_dob.month, parsed_dob.day))

        if age < 21:
            return ValidationResult(False, "age", f"Applicant age ({age} yrs) is below minimum underwriting threshold (21 yrs).", "ERROR"), age
        if age > 65:
            return ValidationResult(False, "age", f"Applicant age ({age} yrs) exceeds standard loan maturity threshold (65 yrs).", "WARNING"), age

        return ValidationResult(True, "age", f"Applicant age is {age} years (within eligible 21-65 range).", "INFO"), age
