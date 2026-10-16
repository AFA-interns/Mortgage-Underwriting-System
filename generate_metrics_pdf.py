"""
Script to generate a publication-quality documentation PDF for:
DOCUMENT INGESTION AGENT - Evaluation Metrics & Rationale
Mortgage Underwriting System (India-focused • Fully automated • No human review in the decision path)
Matching the exact 9-page layout, typography, structure, and professional standards of the reference document.
"""

import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas for adding running headers and running footers on pages > 1."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#555555"))

            # Running Header
            self.drawString(54, 11 * inch - 36, "DOCUMENT INGESTION AGENT — EVALUATION METRICS & RATIONALE")
            self.setStrokeColor(colors.HexColor("#D0D5DD"))
            self.setLineWidth(0.5)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)

            # Running Footer
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(8.5 * inch - 54, 36, page_text)
            self.drawString(54, 36, "Mortgage Underwriting System (India) • Fully Automated Document Ingestion")
            self.line(54, 48, 8.5 * inch - 54, 48)

            self.restoreState()


def generate_pdf(output_filename="Document_Ingestion_Agent_Evaluation_Metrics.pdf"):
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Brand Colors
    primary_color = colors.HexColor("#1E3A8A")   # Deep Navy
    accent_blue = colors.HexColor("#2563EB")     # Bright Accent
    dark_neutral = colors.HexColor("#1F2937")    # Near Black
    body_text_color = colors.HexColor("#374151") # Charcoal Body
    border_gray = colors.HexColor("#D1D5DB")     # Grid Lines

    title_agent_style = ParagraphStyle(
        "CoverAgentHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=15,
    )

    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=1,
        textColor=primary_color,
        spaceAfter=12,
    )

    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        alignment=1,
        textColor=dark_neutral,
        spaceAfter=6,
    )

    cover_tagline_style = ParagraphStyle(
        "CoverTagline",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=20,
    )

    cover_purpose_style = ParagraphStyle(
        "CoverPurpose",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#374151"),
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12.5,
        textColor=accent_blue,
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=11.2,
        textColor=body_text_color,
        spaceAfter=4,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )

    formula_style = ParagraphStyle(
        "Formula_Custom",
        parent=body_style,
        fontName="Courier-Bold",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=1,
        spaceAfter=3,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=10,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=dark_neutral,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell_style,
        fontName="Helvetica-Bold",
    )

    story = []

    # =========================================================================
    # PAGE 1: COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph("DOCUMENT INGESTION AGENT", title_agent_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Evaluation Metrics & Rationale", cover_title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_blue, spaceBefore=4, spaceAfter=2.3 * inch))

    story.append(Paragraph("Mortgage Underwriting System", cover_subtitle_style))
    story.append(Paragraph("India-focused • Fully automated • No human review in the decision path", cover_tagline_style))

    story.append(Spacer(1, 1.4 * inch))
    story.append(
        Paragraph(
            "<b>Purpose:</b> document what each Document Ingestion Agent metric measures, why it was selected, "
            "and how it supports safe, explainable underwriting evaluation when every case is resolved by the agent "
            "without human validation.",
            cover_purpose_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: 1. EVALUATION CONTEXT
    # =========================================================================
    story.append(Paragraph("1. Evaluation Context", h1_style))
    story.append(
        Paragraph(
            "The Document Ingestion Agent is evaluated as a fully automated hybrid system. Its spatial extraction core performs "
            "multi-format document intake, layout text parsing, structured Pydantic schema extraction, field provenance tracking, "
            "deterministic validation, cross-document reconciliation, and finalization. The deterministic layer remains authoritative for all "
            "regulatory and financial rules. No case is routed to a human reviewer: every case ends in an automated outcome, and when "
            "the evidence is uncertain the agent takes the most conservative outcome, never PROCEED.",
            body_style,
        )
    )

    outputs_data = [
        [
            Paragraph("Output", table_header_style),
            Paragraph("Range / Type", table_header_style),
            Paragraph("Meaning", table_header_style),
        ],
        [
            Paragraph("document_type", table_cell_bold),
            Paragraph("Enum (8 classes)", table_cell_style),
            Paragraph("PAN_CARD, AADHAAR, SALARY_SLIP, FORM_16, ITR, BANK_STMT, PROPERTY, UNKNOWN", table_cell_style),
        ],
        [
            Paragraph("field_extractions", table_cell_bold),
            Paragraph("Pydantic Models", table_cell_style),
            Paragraph("Structured borrower KYC, income, banking aggregates, and property specifications", table_cell_style),
        ],
        [
            Paragraph("provenance", table_cell_bold),
            Paragraph("Doc + Page + Snippet", table_cell_style),
            Paragraph("Audit trail establishing the exact source evidence for every extracted value", table_cell_style),
        ],
        [
            Paragraph("confidence", table_cell_bold),
            Paragraph("0–1", table_cell_style),
            Paragraph("Evidence reliability; 0.85 or above is the condition for PROCEED", table_cell_style),
        ],
        [
            Paragraph("gate_triggered", table_cell_bold),
            Paragraph("e.g. missing_docs", table_cell_style),
            Paragraph("Safety gate that fired; selects the automated action", table_cell_style),
        ],
        [
            Paragraph("automated_disposition<br/>(new)", table_cell_bold),
            Paragraph("Enum (4 outcomes)", table_cell_style),
            Paragraph("Outcome of the case, with no human step", table_cell_style),
        ],
    ]

    t_out = Table(outputs_data, colWidths=[110, 110, 284])
    t_out.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_out)
    story.append(Spacer(1, 5))

    outcomes_data = [
        [
            Paragraph("Automated outcome", table_header_style),
            Paragraph("State", table_header_style),
            Paragraph("What happens", table_header_style),
        ],
        [
            Paragraph("PROCEED", table_cell_bold),
            Paragraph("Terminal", table_cell_style),
            Paragraph("All checks pass and confidence is 0.85 or above; data goes to the credit agent as extracted.", table_cell_style),
        ],
        [
            Paragraph("PROCEED_CONSERVATIVE", table_cell_bold),
            Paragraph("Terminal", table_cell_style),
            Paragraph("The case continues on the lower, more cautious verified value; the discrepancy is attached so downstream agents see it.", table_cell_style),
        ],
        [
            Paragraph("REQUEST_RESUBMISSION", table_cell_bold),
            Paragraph("Pending", table_cell_style),
            Paragraph("The agent sends the borrower an automatic request naming the missing, unreadable or conflicting document. The case is parked on a timer and re-enters the pipeline when files arrive.", table_cell_style),
        ],
        [
            Paragraph("CLOSE_UNRESOLVED", table_cell_bold),
            Paragraph("Terminal", table_cell_style),
            Paragraph("The timeout expires, the maximum number of attempts is reached, or a hard conflict stays unresolved; the case is closed with the reasons recorded.", table_cell_style),
        ],
    ]

    t_outcomes = Table(outcomes_data, colWidths=[120, 64, 320])
    t_outcomes.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(t_outcomes)
    story.append(Spacer(1, 5))

    story.append(
        Paragraph(
            "<b>Conservativeness order, most to least:</b> CLOSE_UNRESOLVED, REQUEST_RESUBMISSION, "
            "PROCEED_CONSERVATIVE, PROCEED. When several triggers fire on one case, the most conservative outcome wins. The "
            "same order is used to score false accepts and false rejects (section 7).",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Termination and re-entry.</b> A pending case becomes CLOSE_UNRESOLVED when the resubmission timeout expires or the "
            "maximum number of attempts is reached; both are configuration values (section 7), so every case reaches a terminal outcome. "
            "When files arrive, the whole case is re-evaluated on the union of old and new documents, the new result supersedes the old "
            "one, and the audit trail is append-only.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Three metric families are required: correctness metrics against labeled ground truth, calibration metrics for the confidence "
            "score, and automation and safety metrics measured from the audit trail.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: 2. DATASET AND GROUND TRUTH & 3. CLASSIFICATION METRICS
    # =========================================================================
    story.append(Paragraph("2. Dataset and Ground Truth", h1_style))
    story.append(
        Paragraph(
            "The shipped evaluation dataset contains 40 labeled synthetic cases comprising over 160 individual files. Labels are assigned "
            "independently from model predictions according to underwriting design intent, avoiding self-confirmation. The 25 edge cases "
            "that human review used to catch now each need an expected automated outcome.",
            body_style,
        )
    )

    dataset_data = [
        [
            Paragraph("Case class", table_header_style),
            Paragraph("Cases", table_header_style),
            Paragraph("Rule for the expected automated outcome", table_header_style),
        ],
        [Paragraph("Clean Prime Salaried", table_cell_bold), Paragraph("15", table_cell_style), Paragraph("PROCEED", table_cell_style)],
        [Paragraph("Name Discrepancy", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("Minor spelling variant: PROCEED after re-match. Genuine conflict: REQUEST_RESUBMISSION.", table_cell_style)],
        [Paragraph("Income Variance", table_cell_bold), Paragraph("7", table_cell_style), Paragraph("Within the variance limit: PROCEED_CONSERVATIVE. Beyond it: REQUEST_RESUBMISSION.", table_cell_style)],
        [Paragraph("Missing Docs", table_cell_bold), Paragraph("6", table_cell_style), Paragraph("REQUEST_RESUBMISSION", table_cell_style)],
        [Paragraph("Low-Quality Scans", table_cell_bold), Paragraph("4", table_cell_style), Paragraph("Recoverable by design: PROCEED. Otherwise: REQUEST_RESUBMISSION.", table_cell_style)],
    ]

    t_dataset = Table(dataset_data, colWidths=[120, 44, 340])
    t_dataset.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_dataset)
    story.append(Spacer(1, 4))

    story.append(Paragraph("• Each case receives exactly one expected outcome; the table gives the rule for choosing it. The benchmark scores the first-pass outcome, because no borrower reply is simulated.", bullet_style))
    story.append(Paragraph("• Borderline cases are deliberately included, including minor spelling variants and variable payslip bonuses.", bullet_style))
    story.append(Paragraph("• Safety-gate cases include missing_mandatory_docs, salary_discrepancy, name_contradiction, and unmasked_aadhaar.", bullet_style))
    story.append(Paragraph("• The source does not say which name cases are spelling variants or which income cases exceed the variance limit, so those labels must be set per case. This is a one-time labeling task, not a review step in the live pipeline.", bullet_style))
    story.append(Paragraph("• Add cases with forged or spliced documents; an unattended system has no one to notice them (section 10).", bullet_style))
    story.append(Paragraph("• For production evaluation, supplement the synthetic labels with historical underwritten outcomes.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("3. Classification Metrics", h1_style))
    story.append(Paragraph("Classification metrics evaluate whether the predicted document type matches the labeled ground truth across all 8 classes. None of them depend on a reviewer.", body_style))

    class_metrics_data = [
        [
            Paragraph("Metric", table_header_style),
            Paragraph("Definition", table_header_style),
            Paragraph("Why chosen", table_header_style),
        ],
        [
            Paragraph("Accuracy and balanced accuracy", table_cell_bold),
            Paragraph("Correct predictions ÷ total cases; mean of per-class recall.", table_cell_style),
            Paragraph("Package class mixes are unequal. Balanced accuracy stops a payslip-heavy mix hiding weak Form 16 or Property results.", table_cell_style),
        ],
        [
            Paragraph("Per-class precision, recall, F1", table_cell_bold),
            Paragraph("Precision = TP ÷ (TP + FP); recall = TP ÷ (TP + FN); F1 is their harmonic mean.", table_cell_style),
            Paragraph("Categories have unequal business consequences; BANK_STMT recall is the key safety guardrail.", table_cell_style),
        ],
        [
            Paragraph("Macro and weighted averages", table_cell_bold),
            Paragraph("Equal weight per class; weight by class support.", table_cell_style),
            Paragraph("Macro gives a class-fair view; weighted reflects the real case mix.", table_cell_style),
        ],
        [
            Paragraph("Confusion matrix", table_cell_bold),
            Paragraph("Actual versus predicted type across all 8 classes.", table_cell_style),
            Paragraph("Shows which error occurred: Bank read as Salary Slip is far worse than a scan sent to UNKNOWN.", table_cell_style),
        ],
        [
            Paragraph("Cost-weighted error", table_cell_bold),
            Paragraph("Σ cost[truth][prediction] ÷ total documents.", table_cell_style),
            Paragraph("Errors are asymmetric; BANK read as SALARY has the highest prototype cost because it can book unverified credit.", table_cell_style),
        ],
    ]

    t_class_metrics = Table(class_metrics_data, colWidths=[120, 150, 234])
    t_class_metrics.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_class_metrics)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: PER-CLASS TABLE & ASYMMETRIC COST MATRIX
    # =========================================================================
    class_perf_data = [
        [
            Paragraph("Class", table_header_style),
            Paragraph("Precision tells us", table_header_style),
            Paragraph("Recall tells us", table_header_style),
        ],
        [
            Paragraph("PAN_CARD", table_cell_bold),
            Paragraph("How cleanly PANs are identified; limits false KYC.", table_cell_style),
            Paragraph("Whether mandatory tax identity proof is captured.", table_cell_style),
        ],
        [
            Paragraph("AADHAAR", table_cell_bold),
            Paragraph("How reliably resident Aadhaar cards are identified.", table_cell_style),
            Paragraph("Whether mandatory residential address proof is captured.", table_cell_style),
        ],
        [
            Paragraph("SALARY_SLIP", table_cell_bold),
            Paragraph("Limits false income proofs; avoids unstructured noise.", table_cell_style),
            Paragraph("Whether all submitted monthly earnings periods are caught.", table_cell_style),
        ],
        [
            Paragraph("FORM_16", table_cell_bold),
            Paragraph("How justified annual tax certificate extractions are.", table_cell_style),
            Paragraph("Whether statutory annual income proofs are caught.", table_cell_style),
        ],
        [
            Paragraph("ITR", table_cell_bold),
            Paragraph("How cleanly income tax returns are identified; limits false income proofs.", table_cell_style),
            Paragraph("Whether filed-return income evidence is captured.", table_cell_style),
        ],
        [
            Paragraph("BANK_STMT", table_cell_bold),
            Paragraph("How accurately multi-page transaction ledgers are parsed.", table_cell_style),
            Paragraph("Whether banking cash flows are caught; the most safety-critical recall.", table_cell_style),
        ],
        [
            Paragraph("PROPERTY", table_cell_bold),
            Paragraph("How cleanly collateral title deeds are identified.", table_cell_style),
            Paragraph("Whether property collateral evidence avoids omission.", table_cell_style),
        ],
        [
            Paragraph("UNKNOWN", table_cell_bold),
            Paragraph("How often a file sent to UNKNOWN is truly unclassifiable; every wrong UNKNOWN triggers a borrower request.", table_cell_style),
            Paragraph("Whether unclassifiable files are caught instead of forced into a wrong class.", table_cell_style),
        ],
    ]

    t_class = Table(class_perf_data, colWidths=[90, 207, 207])
    t_class.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_class)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<i>The source report listed only six classes here; ITR and UNKNOWN are added so all 8 classes are covered.</i>", body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("The evaluation uses the following asymmetric prototype cost matrix (PAN = PAN_CARD, SALARY = SALARY_SLIP, BANK = BANK_STMT):", body_style))

    cost_data = [
        [
            Paragraph("Truth \\ Pred", table_header_style),
            Paragraph("PAN", table_header_style),
            Paragraph("AADHAAR", table_header_style),
            Paragraph("SALARY", table_header_style),
            Paragraph("FORM_16", table_header_style),
            Paragraph("BANK", table_header_style),
            Paragraph("PROPERTY", table_header_style),
            Paragraph("UNKNOWN", table_header_style),
        ],
        [Paragraph("BANK", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("10", table_cell_bold), Paragraph("6", table_cell_style), Paragraph("0", table_cell_style), Paragraph("8", table_cell_style), Paragraph("2", table_cell_style)],
        [Paragraph("PAN", table_cell_bold), Paragraph("0", table_cell_style), Paragraph("4", table_cell_style), Paragraph("8", table_cell_style), Paragraph("6", table_cell_style), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("2", table_cell_style)],
        [Paragraph("AADHAAR", table_cell_bold), Paragraph("4", table_cell_style), Paragraph("0", table_cell_style), Paragraph("8", table_cell_style), Paragraph("6", table_cell_style), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("2", table_cell_style)],
        [Paragraph("SALARY", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("0", table_cell_style), Paragraph("3", table_cell_style), Paragraph("10", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("2", table_cell_style)],
        [Paragraph("PROPERTY", table_cell_bold), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("8", table_cell_style), Paragraph("0", table_cell_style), Paragraph("3", table_cell_style)],
    ]

    t_cost = Table(cost_data, colWidths=[64, 62, 62, 62, 62, 62, 65, 65])
    t_cost.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_cost)
    story.append(Spacer(1, 4))
    story.append(Paragraph("Cost-weighted error = Σ cost[truth][prediction] ÷ total documents.", formula_style))

    story.append(
        Paragraph(
            "<b>Without a reviewer:</b> UNKNOWN used to be cheap because a human picked it up. It now triggers "
            "REQUEST_RESUBMISSION, so it stays cheap but costs the borrower a delay. Every other misclassification is uncaught, so "
            "the high costs describe real exposure. The matrix has rows only for BANK, PAN, AADHAAR, SALARY and PROPERTY as true "
            "classes and no ITR column; add rows for FORM_16, ITR and UNKNOWN and an ITR column before treating cost-weighted "
            "error as complete.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<i>Important: the cost matrix is configurable and represents an engineering evaluation choice, not an official regulatory cost schedule.</i>",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: 4. EXTRACTION, 5. RECONCILIATION & 6. CALIBRATION
    # =========================================================================
    story.append(Paragraph("4. Extraction & Validation Metrics", h1_style))
    story.append(
        Paragraph(
            "Extraction metrics evaluate whether granular fields and ledgers are extracted verbatim with full source provenance. A failed "
            "check now selects an automated action instead of waiting for a person.",
            body_style,
        )
    )

    extract_data = [
        [
            Paragraph("Metric", table_header_style),
            Paragraph("Definition", table_header_style),
            Paragraph("Why chosen", table_header_style),
            Paragraph("Automated action on failure", table_header_style),
        ],
        [
            Paragraph("Character and word error rate (CER, WER)", table_cell_bold),
            Paragraph("Levenshtein distance to the reference ÷ reference length.", table_cell_style),
            Paragraph("Separates OCR degradation from downstream parsing rules.", table_cell_style),
            Paragraph("Feeds the low-confidence recovery passes.", table_cell_style),
        ],
        [
            Paragraph("Exact match (EM)", table_cell_bold),
            Paragraph("1.0 if the normalized value equals the label, else 0.0.", table_cell_style),
            Paragraph("Required for discrete identifiers such as PAN (ABCPS1234F) and IFSC (HDFC0001234).", table_cell_style),
            Paragraph("A failed format check lowers confidence and triggers re-extraction.", table_cell_style),
        ],
        [
            Paragraph("Token F1", table_cell_bold),
            Paragraph("Token overlap between predicted and labeled value.", table_cell_style),
            Paragraph("Tolerates variants such as “Limited” versus “Ltd” in employer names.", table_cell_style),
            Paragraph("None; used for scoring only.", table_cell_style),
        ],
        [
            Paragraph("Salary ledger reconciliation", table_cell_bold),
            Paragraph("|Gross − (Net + Deductions)| within ±2.00 (rupees assumed).", table_cell_style),
            Paragraph("Forged payslips often fail simple arithmetic; deterministic checks trap fraud before credit scoring.", table_cell_style),
            Paragraph("Payslip excluded from income; REQUEST_RESUBMISSION.", table_cell_style),
        ],
        [
            Paragraph("Provenance coverage", table_cell_bold),
            Paragraph("Extracted fields with a valid (Doc, Page, Snippet) ÷ all extracted fields.", table_cell_style),
            Paragraph("Keeps every value traceable for audit and for downstream agents. Target 100%.", table_cell_style),
            Paragraph("A field without provenance is re-extracted or dropped, never passed on.", table_cell_style),
        ],
    ]

    t_extract = Table(extract_data, colWidths=[90, 110, 154, 150])
    t_extract.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ])
    )
    story.append(t_extract)
    story.append(Spacer(1, 4))

    story.append(Paragraph("5. Cross-Document Reconciliation Metrics", h1_style))
    story.append(
        Paragraph(
            "Reconciliation metrics evaluate whether the agent cross-examines data across independent documents. Contradiction recall is "
            "the most safety-critical metric and matters more now: a contradiction the agent misses goes straight to the credit agent with no "
            "one to stop it.",
            body_style,
        )
    )

    story.append(Paragraph("• <b>Name and income reconciliation accuracy.</b> Names are matched fuzzily across KYC, salary slips and bank statements; monthly net salary is reconciled against detected bank credits within ±5% tolerance.", bullet_style))
    story.append(Paragraph("• <b>Contradiction detection recall.</b> True contradictions detected ÷ total actual contradictions. Target benchmark is 98.0% or higher.", bullet_style))
    story.append(Paragraph("• <b>Contradiction precision.</b> Real contradictions ÷ contradictions flagged. A false flag sends a resubmission request to a borrower with a clean file.", bullet_style))
    story.append(Paragraph("• <b>Contradiction handling accuracy (new).</b> Detected contradictions where the automated action matches the expected one ÷ all detected contradictions.", bullet_style))

    story.append(
        Paragraph(
            "The benchmark has at most about 15 contradiction cases (8 name, 7 income variance). A perfect recall score on that few "
            "cases is still consistent with a true miss rate of up to about 20% (rule of three: 3 ÷ n), so read 100% on this dataset as a floor, "
            "not proof.",
            body_style,
        )
    )
    story.append(Spacer(1, 3))

    story.append(Paragraph("6. Calibration Metrics", h1_style))
    story.append(
        Paragraph(
            "Calibration asks whether the confidence score means what it claims. A confidence of 0.90 should correspond to roughly a 90% "
            "probability of extraction correctness. Confidence of 0.85 or above is the condition for PROCEED and is now the only gate "
            "between an extraction error and the downstream agents.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>What counts as correct.</b> The source does not define correctness for Brier and ECE. Classification accuracy is 0.9938 and "
            "field exact match is 0.9770, yet every populated bin below shows 100% accuracy, so the baseline appears to score "
            "correctness at the level of the case outcome. Define it explicitly: a case is correct when its automated outcome equals the "
            "expected outcome and every field used downstream is within tolerance of its label.",
            body_style,
        )
    )

    story.append(Paragraph("Brier score = mean squared error between confidence and correctness (1 correct, 0 incorrect). Lower is better.", formula_style))
    story.append(Paragraph("ECE = Σ (|B_m| ÷ N) × |acc(B_m) − conf(B_m)| across 5 confidence bins. 0 is perfect calibration.", formula_style))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: 6. CALIBRATION (CONT) & 7. AUTOMATED OUTCOMES MAPPING
    # =========================================================================
    story.append(
        Paragraph(
            "<b>Gate-passing error rate (new):</b> cases that are not correct and have confidence of 0.85 or above ÷ all cases with confidence of "
            "0.85 or above. This is the rate at which errors get through the gate unseen.",
            body_style,
        )
    )

    bins_data = [
        [
            Paragraph("Confidence interval", table_header_style),
            Paragraph("Case count", table_header_style),
            Paragraph("Mean confidence", table_header_style),
            Paragraph("Actual accuracy", table_header_style),
            Paragraph("Calibration gap", table_header_style),
        ],
        [Paragraph("0.00 – 0.20", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.1000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.20 – 0.40", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.3000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.40 – 0.60", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.5000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.60 – 0.80", table_cell_style), Paragraph("12", table_cell_bold), Paragraph("0.6973", table_cell_style), Paragraph("1.0000", table_cell_style), Paragraph("0.3027", table_cell_style)],
        [Paragraph("0.80 – 1.00", table_cell_style), Paragraph("28", table_cell_bold), Paragraph("0.9142", table_cell_style), Paragraph("1.0000", table_cell_style), Paragraph("0.0858", table_cell_style)],
    ]

    t_bins = Table(bins_data, colWidths=[104, 100, 100, 100, 100])
    t_bins.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ])
    )
    story.append(t_bins)
    story.append(Spacer(1, 3))

    story.append(Paragraph("• <b>Under-confident, not over-confident.</b> All 12 cases in the 0.60–0.80 bin fall below the 0.85 threshold and were correct; they now enter recovery or a resubmission request, which is avoidable friction.", bullet_style))
    story.append(Paragraph("• <b>ECE needs a re-run.</b> Weighting the two populated gaps by case count gives 0.3 × 0.3027 + 0.7 × 0.0858 ≈ 0.151, while the baseline reports 0.1489. At 0.151 the 0.150 target is just missed.", bullet_style))
    story.append(Paragraph("• <b>Gate failures are invisible.</b> Every populated bin has 100% accuracy, so the table cannot show whether a high-confidence extraction is ever wrong. Add wrongly extracted cases to the benchmark.", bullet_style))
    story.append(Paragraph("• <b>Proposed:</b> tighten the ECE target to 0.050 and the gate-passing error rate to 0; recalibrate confidence (for example isotonic regression or Platt scaling) on a larger held-out set and choose the 0.85 threshold from that data.", bullet_style))
    story.append(Paragraph("• <b>Proposed:</b> gate on the lowest confidence among decision-critical fields (name, PAN, net salary, bank credits, property value) as well as the overall score, so one weak field cannot be averaged away.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("7. Automated Outcomes & Safety Metrics", h1_style))
    story.append(
        Paragraph(
            "These replace the straight-through-processing and HITL escalation metrics. Each safety gate maps to an automated action; no "
            "gate suspends a case for human review.",
            body_style,
        )
    )

    gate_action_data = [
        [
            Paragraph("Trigger", table_header_style),
            Paragraph("Automated action", table_header_style),
            Paragraph("Resulting outcome", table_header_style),
        ],
        [
            Paragraph("missing_mandatory_docs", table_cell_bold),
            Paragraph("Send the borrower the list of missing document types and park the case on a timer; no agent can create a missing document.", table_cell_style),
            Paragraph("REQUEST_RESUBMISSION, then CLOSE_UNRESOLVED on timeout or after the maximum attempts.", table_cell_style),
        ],
        [
            Paragraph("salary_discrepancy (net salary vs bank credits outside ±5%)", table_cell_bold),
            Paragraph("Re-extract both figures once; if the gap remains, use the lower of payslip net salary and the average of detected salary credits over the same months.", table_cell_style),
            Paragraph("PROCEED_CONSERVATIVE; above the salary variance limit, REQUEST_RESUBMISSION.", table_cell_style),
        ],
        [
            Paragraph("name_contradiction", table_cell_bold),
            Paragraph("Re-match using deterministic normalization only (initials, name order, transliteration); the similarity threshold is never lowered.", table_cell_style),
            Paragraph("PROCEED if resolved; otherwise REQUEST_RESUBMISSION, then CLOSE_UNRESOLVED.", table_cell_style),
        ],
        [
            Paragraph("unmasked_aadhaar", table_cell_bold),
            Paragraph("Redact the first 8 digits before any extracted value, provenance snippet or log entry is written, so the full number is never stored.", table_cell_style),
            Paragraph("PROCEED, if no other trigger fired.", table_cell_style),
        ],
        [
            Paragraph("Ledger arithmetic mismatch", table_cell_bold),
            Paragraph("Treat the payslip as unreliable, exclude it from income and request a replacement.", table_cell_style),
            Paragraph("REQUEST_RESUBMISSION.", table_cell_style),
        ],
        [
            Paragraph("Confidence below the threshold (including low-quality scans)", table_cell_bold),
            Paragraph("At most two recovery passes: image preprocessing and re-extraction, then a second independent extractor compared field by field; confidence is recomputed after each.", table_cell_style),
            Paragraph("PROCEED if confidence recovers to 0.85; otherwise REQUEST_RESUBMISSION for a rescan.", table_cell_style),
        ],
    ]

    t_gate = Table(gate_action_data, colWidths=[120, 204, 180])
    t_gate.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ])
    )
    story.append(t_gate)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 7: CONFIGURATION PARAMETERS & AUTOMATED OUTCOMES METRICS
    # =========================================================================
    story.append(Paragraph("Configuration parameters. Every threshold the flow depends on is listed here so none is left implicit.", body_style))

    config_data = [
        [
            Paragraph("Parameter", table_header_style),
            Paragraph("Used for", table_header_style),
            Paragraph("Value", table_header_style),
        ],
        [Paragraph("Confidence threshold", table_cell_bold), Paragraph("Condition for PROCEED", table_cell_style), Paragraph("0.85 (source)", table_cell_style)],
        [Paragraph("Income reconciliation tolerance", table_cell_bold), Paragraph("Net salary versus bank credits", table_cell_style), Paragraph("±5% (source)", table_cell_style)],
        [Paragraph("Ledger tolerance", table_cell_bold), Paragraph("Gross versus Net + Deductions", table_cell_style), Paragraph("±2.00, rupees assumed (source)", table_cell_style)],
        [Paragraph("Recovery passes per case", table_cell_bold), Paragraph("Low-confidence recovery", table_cell_style), Paragraph("2 (preprocessing, second extractor)", table_cell_style)],
        [Paragraph("Salary variance limit", table_cell_bold), Paragraph("PROCEED_CONSERVATIVE versus REQUEST_RESUBMISSION", table_cell_style), Paragraph("To be set; not defined in the source", table_cell_style)],
        [Paragraph("Resubmission timeout", table_cell_bold), Paragraph("Pending case to CLOSE_UNRESOLVED", table_cell_style), Paragraph("To be set; not defined in the source", table_cell_style)],
        [Paragraph("Maximum resubmission attempts", table_cell_bold), Paragraph("Guarantees every case terminates", table_cell_style), Paragraph("To be set; not defined in the source", table_cell_style)],
        [Paragraph("Circuit-breaker limits", table_cell_bold), Paragraph("Allowed drift from the rolling baseline (section 10)", table_cell_style), Paragraph("To be set; not defined in the source", table_cell_style)],
    ]

    t_config = Table(config_data, colWidths=[150, 184, 170])
    t_config.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ])
    )
    story.append(t_config)
    story.append(Spacer(1, 3))
    story.append(Paragraph("<i>Cases that depend on a value marked “To be set” cannot be scored until it is fixed.</i>", body_style))
    story.append(Spacer(1, 3))

    auto_metrics_data = [
        [
            Paragraph("Metric", table_header_style),
            Paragraph("Definition", table_header_style),
            Paragraph("Proposed target", table_header_style),
        ],
        [
            Paragraph("automation_rate", table_cell_bold),
            Paragraph("Cases that reach an outcome (including REQUEST_RESUBMISSION) with no human touch ÷ all cases.", table_cell_style),
            Paragraph("100%", table_cell_style),
        ],
        [
            Paragraph("stuck_case_rate", table_cell_bold),
            Paragraph("Cases with no outcome, or pending past the timeout ÷ all cases.", table_cell_style),
            Paragraph("0", table_cell_style),
        ],
        [
            Paragraph("disposition_accuracy", table_cell_bold),
            Paragraph("Cases whose outcome equals the expected outcome ÷ all cases.", table_cell_style),
            Paragraph("0.95 or higher", table_cell_style),
        ],
        [
            Paragraph("false_accept_rate", table_cell_bold),
            Paragraph("Cases whose outcome is less conservative than expected ÷ cases whose expected outcome is more conservative than PROCEED.", table_cell_style),
            Paragraph("0 on the benchmark", table_cell_style),
        ],
        [
            Paragraph("false_reject_rate", table_cell_bold),
            Paragraph("Cases whose outcome is more conservative than expected ÷ cases whose expected outcome is less conservative than CLOSE_UNRESOLVED.", table_cell_style),
            Paragraph("Track the trend", table_cell_style),
        ],
        [
            Paragraph("edge_case_containment", table_cell_bold),
            Paragraph("Edge cases whose outcome is at least as conservative as expected ÷ edge cases (25 in the benchmark).", table_cell_style),
            Paragraph("25 of 25", table_cell_style),
        ],
        [
            Paragraph("conservative_value_error", table_cell_bold),
            Paragraph("PROCEED_CONSERVATIVE cases where the value used exceeds the verified value ÷ PROCEED_CONSERVATIVE cases.", table_cell_style),
            Paragraph("0", table_cell_style),
        ],
        [
            Paragraph("recovery_rate", table_cell_bold),
            Paragraph("Cases reaching PROCEED after recovery ÷ cases entering it.", table_cell_style),
            Paragraph("Track the trend", table_cell_style),
        ],
        [
            Paragraph("resubmission_resolution_rate", table_cell_bold),
            Paragraph("Resubmission requests answered and resolved before timeout ÷ requests sent.", table_cell_style),
            Paragraph("Track the trend", table_cell_style),
        ],
        [
            Paragraph("auto_proceed_rate", table_cell_bold),
            Paragraph("Cases ending PROCEED ÷ all cases; replaces stp_rate.", table_cell_style),
            Paragraph("Informational", table_cell_style),
        ],
    ]

    t_auto_metrics = Table(auto_metrics_data, colWidths=[120, 264, 120])
    t_auto_metrics.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ])
    )
    story.append(t_auto_metrics)
    story.append(Spacer(1, 4))

    story.append(
        Paragraph(
            "False accepts and false rejects are scored on the conservativeness order in section 1. A metric whose denominator is empty is "
            "reported as n/a, not as 0 or 1. Unchanged and label-free: gate_trigger_counts, mean_confidence, below_threshold_rate and "
            "provenance_coverage; below_threshold_rate now measures how often recovery starts. Retired: stp_rate and "
            "hitl_escalation_rate. On the benchmark the expected auto_proceed_rate is the share of cases labeled PROCEED: at least 15 "
            "of 40 (37.5%), more if recoverable scans and spelling variants are labeled PROCEED. Do not push it up at the expense of "
            "false_accept_rate.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 8: 8. CURRENT BASELINE AND TARGETS & 9. WHY CHOSEN
    # =========================================================================
    story.append(Paragraph("8. Current Baseline and Targets", h1_style))
    story.append(
        Paragraph(
            "Correctness baselines carry over from the original benchmark. The new metrics have no baseline until the automated flow is "
            "built and run, and recovery and recalibration may shift the extraction and calibration numbers, so re-run all of them after the "
            "change.",
            body_style,
        )
    )

    baseline_targets_data = [
        [
            Paragraph("Evaluation Metric", table_header_style),
            Paragraph("Baseline Value", table_header_style),
            Paragraph("Target Benchmark", table_header_style),
            Paragraph("Note", table_header_style),
        ],
        [Paragraph("Document Classification Accuracy", table_cell_bold), Paragraph("0.9938 (99.38%)", table_cell_style), Paragraph("0.950 or higher", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Classification Balanced Accuracy", table_cell_bold), Paragraph("0.9956 (99.56%)", table_cell_style), Paragraph("0.950 or higher", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Asymmetric Cost-Weighted Error", table_cell_bold), Paragraph("0.0124", table_cell_style), Paragraph("0.150 or lower", table_cell_style), Paragraph("Cost matrix incomplete", table_cell_style)],
        [Paragraph("Field Extraction Exact Match (EM)", table_cell_bold), Paragraph("0.9770 (97.70%)", table_cell_style), Paragraph("0.920 or higher", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Field Extraction Token F1 Score", table_cell_bold), Paragraph("0.9878 (98.78%)", table_cell_style), Paragraph("0.950 or higher", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("OCR Character Error Rate (CER)", table_cell_bold), Paragraph("0.0142 (1.42%)", table_cell_style), Paragraph("0.030 or lower", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Contradiction Detection Recall (Safety)", table_cell_bold), Paragraph("1.0000 (100.00%)", table_cell_bold), Paragraph("0.980 or higher", table_cell_style), Paragraph("Too few cases to certify", table_cell_style)],
        [Paragraph("Contradiction Precision", table_cell_bold), Paragraph("1.0000 (100.00%)", table_cell_style), Paragraph("0.900 or higher", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Brier Score", table_cell_bold), Paragraph("0.0346", table_cell_style), Paragraph("0.100 or lower", table_cell_style), Paragraph("Unchanged", table_cell_style)],
        [Paragraph("Expected Calibration Error (ECE)", table_cell_bold), Paragraph("0.1489 reported; about 0.151 from bins", table_cell_style), Paragraph("0.150 or lower; proposed 0.050", table_cell_style), Paragraph("Re-run", table_cell_style)],
        [Paragraph("Straight-Through Processing (STP) Rate", table_cell_bold), Paragraph("0.3750 (37.50%)", table_cell_style), Paragraph("None", table_cell_style), Paragraph("Retired", table_cell_style)],
        [Paragraph("HITL Escalation Rate", table_cell_bold), Paragraph("0.6250 (62.50%)", table_cell_style), Paragraph("None", table_cell_style), Paragraph("Retired", table_cell_style)],
        [Paragraph("Automation Rate", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("100%", table_cell_style), Paragraph("New", table_cell_style)],
        [Paragraph("Stuck-Case Rate", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("0", table_cell_style), Paragraph("New", table_cell_style)],
        [Paragraph("Disposition Accuracy", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("0.95 or higher (proposed)", table_cell_style), Paragraph("New", table_cell_style)],
        [Paragraph("Edge-Case Containment", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("25 of 25", table_cell_style), Paragraph("New", table_cell_style)],
        [Paragraph("False-Accept Rate", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("0", table_cell_style), Paragraph("New", table_cell_style)],
        [Paragraph("Gate-Passing Error Rate", table_cell_bold), Paragraph("Not yet measured", table_cell_style), Paragraph("0", table_cell_style), Paragraph("New", table_cell_style)],
    ]

    t_base_targets = Table(baseline_targets_data, colWidths=[150, 130, 130, 94])
    t_base_targets.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ])
    )
    story.append(t_base_targets)
    story.append(Spacer(1, 3))
    story.append(Paragraph("<i>These values are baseline results for the shipped benchmark dataset and should be interpreted as an engineering benchmark.</i>", body_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("9. Why This Metric Set Was Chosen", h1_style))
    story.append(Paragraph("• <b>Safety:</b> contradiction recall, false-accept rate, confusion matrices, and cost-weighted error emphasize the asymmetric harm of corrupted borrower financials.", bullet_style))
    story.append(Paragraph("• <b>Class fairness:</b> balanced accuracy and macro metrics prevent payslip-heavy document distributions from hiding weak classification on rare deeds.", bullet_style))
    story.append(Paragraph("• <b>Extraction fidelity:</b> Exact Match, Token F1, and CER test whether granular entities and financial figures are extracted without distortion.", bullet_style))
    story.append(Paragraph("• <b>Trust in automation:</b> Brier, ECE, reliability bins, and the gate-passing error rate test whether confidence is reliable enough to be the only gate for PROCEED.", bullet_style))
    story.append(Paragraph("• <b>Automation health:</b> automation rate, stuck-case rate, disposition accuracy, and recovery and resubmission rates show whether the agent resolves cases correctly on its own.", bullet_style))
    story.append(Paragraph("• <b>Auditability:</b> provenance coverage guarantees full source verification rather than treating the LLM/OCR as an unverifiable authority.", bullet_style))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 9: 10. RISKS & SAFEGUARDS, 11. FUTURE SCOPE & 12. GOVERNANCE
    # =========================================================================
    story.append(Paragraph("10. Risks and Safeguards", h1_style))
    story.append(Paragraph("The current benchmark cannot show that an unattended agent is safe; it can only show that nothing has failed yet.", body_style))

    story.append(Paragraph("• <b>Too few cases.</b> The baseline figures are consistent with 161 documents and a single error that cost 2 (160 ÷ 161 = 0.9938; 2 ÷ 161 = 0.0124), so one document moves accuracy by about 0.6 points. With at most about 15 contradiction cases and no wrongly extracted cases, perfect scores say little about the true error rate. Grow the benchmark with adversarial and wrongly extracted cases and add historical underwritten outcomes.", bullet_style))
    story.append(Paragraph("• <b>Digital tampering is now required, not future scope.</b> A forged document that is internally consistent passes every check in this report, and no reviewer would see the splice. Quantify precision and recall on image splicing, font inconsistencies, and PDF metadata modifications.", bullet_style))
    story.append(Paragraph("• <b>Loosened matching.</b> An automated re-match can “resolve” a genuine conflict by relaxing the matcher. Limit it to deterministic normalizations and never lower the similarity threshold.", bullet_style))
    story.append(Paragraph("• <b>Sensitive data.</b> Unmasked Aadhaar numbers must be redacted before they reach provenance snippets, logs or the audit trail, not only in the final stored copy.", bullet_style))
    story.append(Paragraph("• <b>Downstream inheritance.</b> Credit and decision agents now receive data no person has looked at. Each PROCEED_CONSERVATIVE case must carry its flag forward, and a flagged value is treated as unverified.", bullet_style))
    story.append(Paragraph("• <b>Accountability.</b> The source describes this component as decision-support inside a human-in-the-loop architecture. Confirm with compliance that unattended operation is acceptable under the lender's own policy and the applicable RBI requirements before going live.", bullet_style))

    story.append(
        Paragraph(
            "<b>Safeguards that do not block a case:</b> a circuit breaker that, when below_threshold_rate, gate_trigger_counts or the "
            "resubmission rate drifts past its limit, stops issuing PROCEED, holds new cases in an automatic retry queue without contacting "
            "borrowers, and alerts engineering about the system (not about individual cases); a full provenance and audit trail for every "
            "decision; and optional after-the-fact sampling of auto-processed cases, which nothing waits on and whose results become "
            "production labels. The agent is fully automated without the sampling.",
            body_style,
        )
    )
    story.append(Spacer(1, 3))

    story.append(Paragraph("11. Future Evaluation Scope", h1_style))
    story.append(Paragraph("• <b>Multilingual KYC extraction:</b> benchmark performance across Hindi, Tamil, Telugu, and Marathi regional identity documents.", bullet_style))
    story.append(Paragraph("• <b>Per-segment slicing:</b> evaluate performance by employer tier, income band, scan resolution, and bank statement format.", bullet_style))
    story.append(Paragraph("• <b>Latency and cost:</b> tokens, wall-clock time, and OCR compute cost per multi-page document bundle, including the cost of recovery passes.", bullet_style))
    story.append(Paragraph("• <b>Resubmission simulation:</b> replay borrower replies so the benchmark can score final outcomes as well as first-pass outcomes.", bullet_style))
    story.append(Spacer(1, 3))

    story.append(Paragraph("12. Implementation, Reproducibility & Governance Note", h1_style))
    story.append(Paragraph("The existing commands still reproduce the baseline:", body_style))

    cli_box_data = [
        [
            Paragraph(
                "<code>python -m src.evaluation.eval_cli<br/>"
                "python -m src.evaluation.eval_cli --output evaluation_report.json<br/>"
                "python -m pytest tests/ -v</code>",
                formula_style,
            )
        ]
    ]
    t_cli = Table(cli_box_data, colWidths=[504])
    t_cli.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_gray),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_cli)
    story.append(Spacer(1, 3))

    story.append(
        Paragraph(
            "The evaluation CLI described in the source reports the retired HITL metrics. The new metrics in section 7 need to be added to "
            "it, and the expected-outcome labels from section 2 added to the dataset. The agent's gate logic also has to change to "
            "implement the automated actions; this report specifies the metrics and does not change the code.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "The Document Ingestion Agent remains an evidentiary extraction and reconciliation component, but in this version it acts "
            "without a reviewer. The ±5% tolerance, the salary variance limit, the cost matrix and every target marked as proposed are "
            "engineering choices; they should not be represented as official RBI rules or regulatory requirements.",
            body_style,
        )
    )

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated evaluation metrics PDF: '{output_filename}'")


if __name__ == "__main__":
    generate_pdf()
