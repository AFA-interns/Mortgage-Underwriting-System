"""
Script to generate a publication-quality documentation PDF for:
DOCUMENT INGESTION AGENT - Evaluation Metrics & Rationale
Matching the exact layout, typography, structure, and professional standards of the sample PDF.
"""

import os
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
    """Canvas for adding page numbers and running headers on pages > 1."""

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
            self.drawString(54, 36, "Mortgage Underwriting System (India) • Decision-Support & Human-in-the-Loop")
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

    # Custom styles
    primary_color = colors.HexColor("#1E3A8A")  # Deep Navy Blue
    accent_blue = colors.HexColor("#2563EB")
    dark_neutral = colors.HexColor("#1F2937")
    body_text_color = colors.HexColor("#374151")

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
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=accent_blue,
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=body_text_color,
        spaceAfter=4,
    )

    body_bold = ParagraphStyle(
        "BodyBold_Custom",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    formula_style = ParagraphStyle(
        "Formula_Custom",
        parent=body_style,
        fontName="Courier-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=1,
        spaceAfter=3,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
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
    story.append(Spacer(1, 2.0 * inch))
    story.append(Paragraph("DOCUMENT INGESTION AGENT", title_agent_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Evaluation Metrics & Rationale", cover_title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent_blue, spaceBefore=4, spaceAfter=2.4 * inch))

    story.append(Paragraph("Mortgage Underwriting System", cover_subtitle_style))
    story.append(Paragraph("India-focused • Decision-support • Human-in-the-loop", cover_tagline_style))

    story.append(Spacer(1, 1.2 * inch))
    story.append(
        Paragraph(
            "<b>Purpose:</b> document what each Document Ingestion Agent metric measures, why it was selected, "
            "and how it supports safe, explainable underwriting evaluation.",
            cover_purpose_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: CONTEXT, DATASET & CLASSIFICATION INTRO
    # =========================================================================
    story.append(Paragraph("1. Evaluation Context", h1_style))
    story.append(
        Paragraph(
            "The Document Ingestion Agent is evaluated as a hybrid system. Its spatial extraction core performs "
            "multi-format document intake, layout text parsing, structured Pydantic schema extraction, field provenance "
            "tracking, deterministic validation, cross-document reconciliation, and finalization with hard safety gates. "
            "The deterministic layer remains authoritative for all regulatory and financial rules.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "For each application, the key outputs are the classified document type, extracted borrower & property "
            "fields, a 0–1 confidence score representing evidence reliability, cross-document contradiction flags, "
            "and the safety gate that was triggered, if any.",
            body_style,
        )
    )

    # Context Table
    context_data = [
        [
            Paragraph("Output", table_header_style),
            Paragraph("Range / Type", table_header_style),
            Paragraph("Meaning", table_header_style),
        ],
        [
            Paragraph("document_type", table_cell_bold),
            Paragraph("Enum (8 classes)", table_cell_style),
            Paragraph("Classified document type (PAN, Aadhaar, Payslip, Form 16, ITR, Bank, Property, Unknown)", table_cell_style),
        ],
        [
            Paragraph("field_extractions", table_cell_bold),
            Paragraph("Pydantic Models", table_cell_style),
            Paragraph("Structured borrower KYC, income, banking aggregates, and property specifications", table_cell_style),
        ],
        [
            Paragraph("provenance", table_cell_bold),
            Paragraph("Doc + Page + Snippet", table_cell_style),
            Paragraph("Audit trail establishing exact source evidence for every extracted value", table_cell_style),
        ],
        [
            Paragraph("confidence", table_cell_bold),
            Paragraph("0–1", table_cell_style),
            Paragraph("Evidence reliability and gateway for auto-processing (threshold ≥ 0.85)", table_cell_style),
        ],
        [
            Paragraph("gate_triggered", table_cell_bold),
            Paragraph("e.g. missing_docs", table_cell_style),
            Paragraph("Safety gate that suspended the case for Human-in-the-Loop review", table_cell_style),
        ],
    ]

    t_context = Table(context_data, colWidths=[110, 110, 284])
    t_context.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(t_context)
    story.append(Spacer(1, 6))

    story.append(
        Paragraph(
            "Two metric families are therefore required: (1) correctness metrics, which compare predictions against "
            "labeled ground truth, and (2) operational metrics, which measure how the system behaves from its audit trail "
            "without requiring labels.",
            body_style,
        )
    )

    story.append(Paragraph("2. Dataset and Ground Truth", h1_style))
    story.append(
        Paragraph(
            "The shipped evaluation dataset contains 40 labeled synthetic cases comprising over 160 individual files. "
            "Labels are assigned independently from model predictions according to underwriting design intent, avoiding self-confirmation.",
            body_style,
        )
    )
    story.append(Paragraph("• <b>Class distribution:</b> 15 Clean Prime Salaried, 8 Name Discrepancy, 7 Income Variance, 6 Missing Docs, and 4 Low-Quality Scans.", bullet_style))
    story.append(Paragraph("• Borderline cases are deliberately included, including minor spelling variants and variable payslip bonuses.", bullet_style))
    story.append(Paragraph("• Safety-gate cases include missing_mandatory_docs, salary_discrepancy, name_contradiction, and unmasked_aadhaar.", bullet_style))
    story.append(Paragraph("• For production evaluation, the synthetic labels should be supplemented with historical underwritten outcomes.", bullet_style))

    story.append(Paragraph("3. Classification Metrics", h1_style))
    story.append(Paragraph("Classification metrics evaluate whether the predicted document type matches the labeled ground truth across all 8 classes.", body_style))

    story.append(Paragraph("3.1 Accuracy and Balanced Accuracy", h2_style))
    story.append(Paragraph("Accuracy = correct predictions ÷ total cases.", formula_style))
    story.append(Paragraph("Balanced accuracy = mean of the recall of the classes.", formula_style))
    story.append(
        Paragraph(
            "<b>Significance:</b> Accuracy provides a quick overall correctness measure, while balanced accuracy prevents a dominant class "
            "(such as multiple payslips) from hiding poor performance in minority classes (such as Form 16 or Property Deeds).",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Why chosen:</b> Underwriting packages contain unequal class distributions. A system that overuses SALARY_SLIP could appear accurate "
            "while failing on PROPERTY_DEED. Balanced accuracy gives each class equal importance.",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: PER-CLASS, MACRO, CONFUSION & COST MATRIX
    # =========================================================================
    story.append(Paragraph("3.2 Per-Class Precision, Recall and F1", h2_style))
    story.append(Paragraph("Precision = TP ÷ (TP + FP). Recall = TP ÷ (TP + FN). F1 is the harmonic mean of precision and recall.", formula_style))

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
            Paragraph("BANK_STMT", table_cell_bold),
            Paragraph("How accurately multi-page transaction ledgers are parsed.", table_cell_style),
            Paragraph("Whether banking cash flows are caught; most safety-critical recall.", table_cell_style),
        ],
        [
            Paragraph("PROPERTY", table_cell_bold),
            Paragraph("How cleanly collateral title deeds are identified.", table_cell_style),
            Paragraph("Whether property collateral evidence avoids omission.", table_cell_style),
        ],
    ]

    t_class = Table(class_perf_data, colWidths=[95, 204, 205])
    t_class.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ])
    )
    story.append(t_class)
    story.append(Spacer(1, 4))

    story.append(
        Paragraph(
            "<b>Why chosen:</b> the document categories do not have equal business consequences. A false classification on a Bank Statement can "
            "cause unverified debt calculations, so BANK_STATEMENT recall is a key safety guardrail. F1 provides a compact per-class balance.",
            body_style,
        )
    )

    story.append(Paragraph("3.3 Macro and Weighted Averages", h2_style))
    story.append(Paragraph("Macro averages treat all classes equally; weighted averages weight each class by its support.", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> macro provides a class-fair view, while weighted averages reflect the actual case mix.", body_style))

    story.append(Paragraph("3.4 Confusion Matrix", h2_style))
    story.append(Paragraph("The confusion matrix tabulates actual versus predicted document types across all 8 classes.", body_style))
    story.append(
        Paragraph(
            "<b>Why chosen:</b> it reveals the type of error rather than reducing performance to one scalar. For example, misclassifying a Bank Statement "
            "as a Salary Slip is materially more dangerous than routing an ambiguous scan to UNKNOWN.",
            body_style,
        )
    )

    story.append(Paragraph("3.5 Cost-Weighted Error", h2_style))
    story.append(Paragraph("The evaluation uses the following asymmetric prototype cost matrix:", body_style))

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

    t_cost = Table(cost_data, colWidths=[65, 62, 62, 62, 62, 62, 65, 64])
    t_cost.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(t_cost)
    story.append(Spacer(1, 3))

    story.append(Paragraph("Cost-weighted error = Σ cost[truth][prediction] ÷ total documents.", formula_style))
    story.append(
        Paragraph(
            "<b>Why chosen:</b> ordinary accuracy treats every error equally, but underwriting errors are asymmetric. A BANK→SALARY error has the highest "
            "prototype cost because it can book unverified credit. Classifying ambiguous files as UNKNOWN carries low cost by providing a safe human-review path. "
            "<br/><i>Important: the cost matrix is configurable and represents an engineering evaluation choice, not an official regulatory cost schedule.</i>",
            body_style,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: EXTRACTION, RECONCILIATION & CALIBRATION METRICS
    # =========================================================================
    story.append(Paragraph("4. Extraction & Validation Metrics", h1_style))
    story.append(Paragraph("Extraction metrics evaluate whether granular fields and ledgers are extracted verbatim with full source provenance.", body_style))

    story.append(Paragraph("4.1 Character Error Rate (CER) and Word Error Rate (WER)", h2_style))
    story.append(Paragraph("CER = LevenshteinDistance(Ref_chars, Pred_chars) ÷ Length(Ref_chars).", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> isolates whether field parsing failures stem from OCR text degradation versus downstream regex rules.", body_style))

    story.append(Paragraph("4.2 Exact Match (EM) and Token F1 Score", h2_style))
    story.append(Paragraph("Exact Match = 1.0 if normalized string matches ground truth verbatim, else 0.0.", formula_style))
    story.append(
        Paragraph(
            "<b>Why chosen:</b> Exact Match is critical for discrete identifiers (PAN: ABCPS1234F, IFSC: HDFC0001234), while Token F1 accommodates "
            "minor word permutations in multi-word entities (Employer: 'Tata Consultancy Services Ltd' vs 'Tata Consultancy Services Limited').",
            body_style,
        )
    )

    story.append(Paragraph("4.3 Salary Ledger Arithmetic Reconciliation Rate", h2_style))
    story.append(Paragraph("Ledger Accuracy = |Gross Salary − (Net Salary + Deductions)| ≤ ₹2.00.", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> forged payslips frequently exhibit arithmetic mismatches. Deterministic math checks trap fraud before credit scoring.", body_style))

    story.append(Paragraph("4.4 Field Provenance Coverage Rate", h2_style))
    story.append(Paragraph("Provenance Coverage = Extracted fields with valid (Doc, Page, Snippet) ÷ Total extracted fields.", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> ensures 100% auditability for regulatory compliance and rapid human-in-the-loop verification.", body_style))

    story.append(Paragraph("5. Cross-Document Reconciliation Metrics", h1_style))
    story.append(Paragraph("Reconciliation metrics evaluate whether the agent successfully cross-examines data across independent documents.", body_style))

    story.append(Paragraph("5.1 Name Resolution and Income Reconciliation Accuracy", h2_style))
    story.append(
        Paragraph(
            "<b>Significance:</b> Evaluates fuzzy matching across KYC, salary slips, and bank statements, and reconciles monthly net salary against "
            "detected bank deposit credits within ±5% tolerance.",
            body_style,
        )
    )

    story.append(Paragraph("5.2 Contradiction Detection Recall (Safety-Critical Guardrail)", h2_style))
    story.append(Paragraph("Contradiction Recall = True Contradictions Detected ÷ Total Actual Contradictions.", formula_style))
    story.append(
        Paragraph(
            "<b>Why chosen:</b> <b>This is the most safety-critical recall metric.</b> Failing to catch a salary discrepancy or identity conflict allows "
            "corrupted data to reach downstream credit and decision agents. Target benchmark is ≥ 98.0%.",
            body_style,
        )
    )

    # =========================================================================
    # SECTION 6: CALIBRATION METRICS (6.1 & 6.2 on Page 4)
    # =========================================================================
    story.append(Paragraph("6. Calibration Metrics", h1_style))
    story.append(
        Paragraph(
            "Calibration asks whether the confidence score means what it claims. A confidence of 0.90 should correspond approximately to a 90% "
            "probability of extraction correctness. This is vital because the pipeline uses confidence ≥ 0.85 as the gateway for auto-processing.",
            body_style,
        )
    )

    story.append(Paragraph("6.1 Brier Score", h2_style))
    story.append(Paragraph("Brier score = Mean squared error between confidence and correctness (1 for correct, 0 for incorrect). Lower is better; 0 is perfect.", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> provides one scalar reflecting correctness and confidence quality. Overconfidence is penalized heavily.", body_style))

    story.append(Paragraph("6.2 Expected Calibration Error (ECE)", h2_style))
    story.append(Paragraph("ECE = Σ (|B_m| ÷ N) × |acc(B_m) − conf(B_m)| across 5 confidence bins. 0 represents perfect calibration.", formula_style))
    story.append(Paragraph("<b>Why chosen:</b> directly tests the operational meaning of the 0.85 confidence threshold across operational tiers.", body_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: RELIABILITY BINS, RUNTIME METRICS & BASELINE RESULTS
    # =========================================================================
    story.append(Paragraph("6.3 Reliability Bins", h2_style))
    story.append(Paragraph("Reliability bins report the confidence interval, case count, mean confidence, and actual accuracy for each bin:", body_style))

    bin_data = [
        [
            Paragraph("Confidence Interval", table_header_style),
            Paragraph("Case Count", table_header_style),
            Paragraph("Mean Confidence", table_header_style),
            Paragraph("Actual Accuracy", table_header_style),
            Paragraph("Calibration Gap", table_header_style),
        ],
        [Paragraph("0.00 – 0.20", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.1000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.20 – 0.40", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.3000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.40 – 0.60", table_cell_style), Paragraph("0", table_cell_style), Paragraph("0.5000", table_cell_style), Paragraph("0.0000", table_cell_style), Paragraph("0.0000", table_cell_style)],
        [Paragraph("0.60 – 0.80", table_cell_style), Paragraph("12", table_cell_bold), Paragraph("0.6973", table_cell_style), Paragraph("1.0000", table_cell_style), Paragraph("0.3027", table_cell_style)],
        [Paragraph("0.80 – 1.00", table_cell_style), Paragraph("28", table_cell_bold), Paragraph("0.9142", table_cell_style), Paragraph("1.0000", table_cell_style), Paragraph("0.0858", table_cell_style)],
    ]

    t_bins = Table(bin_data, colWidths=[104, 100, 100, 100, 100])
    t_bins.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ])
    )
    story.append(t_bins)
    story.append(Spacer(1, 2))
    story.append(Paragraph("<b>Why chosen:</b> diagnostic view behind ECE showing calibration across confidence bands.", body_style))

    story.append(Paragraph("7. Runtime / Operational Metrics", h1_style))
    story.append(Paragraph("Operational metrics require no ground-truth labels and measure pipeline health from audit logs:", body_style))

    ops_table_data = [
        [
            Paragraph("Metric", table_header_style),
            Paragraph("Definition / Significance", table_header_style),
            Paragraph("Why It Was Chosen", table_header_style),
        ],
        [
            Paragraph("stp_rate", table_cell_bold),
            Paragraph("Straight-Through Processing: 1 − hitl_rate.", table_cell_style),
            Paragraph("Shows efficiency gained through automation.", table_cell_style),
        ],
        [
            Paragraph("hitl_escalation_rate", table_cell_bold),
            Paragraph("Applications routed to human review ÷ all cases.", table_cell_style),
            Paragraph("Measures human-review load and queue depth.", table_cell_style),
        ],
        [
            Paragraph("mean_confidence", table_cell_bold),
            Paragraph("Average overall confidence across applications.", table_cell_style),
            Paragraph("Provides overall view of evidence quality.", table_cell_style),
        ],
        [
            Paragraph("below_threshold_rate", table_cell_bold),
            Paragraph("Share of applications below 0.85 confidence.", table_cell_style),
            Paragraph("Shows how often low-confidence gate fires.", table_cell_style),
        ],
        [
            Paragraph("gate_trigger_counts", table_cell_bold),
            Paragraph("Count per safety gate trigger (Missing, Mismatch, Variance).", table_cell_style),
            Paragraph("Identifies dominant operational defect.", table_cell_style),
        ],
        [
            Paragraph("provenance_coverage", table_cell_bold),
            Paragraph("Share of extracted values linked to source bounding text.", table_cell_style),
            Paragraph("Guarantees 100% auditability for compliance.", table_cell_style),
        ],
    ]

    t_ops = Table(ops_table_data, colWidths=[110, 195, 199])
    t_ops.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ])
    )
    story.append(t_ops)
    story.append(Spacer(1, 2))

    story.append(Paragraph("8. Current Baseline on the Shipped Benchmark Dataset", h1_style))

    baseline_data = [
        [
            Paragraph("Evaluation Metric", table_header_style),
            Paragraph("Baseline Value", table_header_style),
            Paragraph("Target Benchmark", table_header_style),
        ],
        [Paragraph("Document Classification Accuracy", table_cell_bold), Paragraph("0.9938 (99.38%)", table_cell_style), Paragraph("≥ 0.950", table_cell_style)],
        [Paragraph("Classification Balanced Accuracy", table_cell_bold), Paragraph("0.9956 (99.56%)", table_cell_style), Paragraph("≥ 0.950", table_cell_style)],
        [Paragraph("Asymmetric Cost-Weighted Error", table_cell_bold), Paragraph("0.0124", table_cell_style), Paragraph("≤ 0.150", table_cell_style)],
        [Paragraph("Field Extraction Exact Match (EM)", table_cell_bold), Paragraph("0.9770 (97.70%)", table_cell_style), Paragraph("≥ 0.920", table_cell_style)],
        [Paragraph("Field Extraction Token F1 Score", table_cell_bold), Paragraph("0.9878 (98.78%)", table_cell_style), Paragraph("≥ 0.950", table_cell_style)],
        [Paragraph("OCR Character Error Rate (CER)", table_cell_bold), Paragraph("0.0142 (1.42%)", table_cell_style), Paragraph("≤ 0.030", table_cell_style)],
        [Paragraph("Contradiction Detection Recall (Safety)", table_cell_bold), Paragraph("1.0000 (100.00%)", table_cell_bold), Paragraph("≥ 0.980", table_cell_style)],
        [Paragraph("Contradiction Precision", table_cell_bold), Paragraph("1.0000 (100.00%)", table_cell_style), Paragraph("≥ 0.900", table_cell_style)],
        [Paragraph("Brier Score", table_cell_bold), Paragraph("0.0346", table_cell_style), Paragraph("≤ 0.100", table_cell_style)],
        [Paragraph("Expected Calibration Error (ECE)", table_cell_bold), Paragraph("0.1489", table_cell_style), Paragraph("≤ 0.150", table_cell_style)],
        [Paragraph("Straight-Through Processing (STP) Rate", table_cell_bold), Paragraph("0.3750 (37.50%)", table_cell_style), Paragraph("Reflects 40-case mix", table_cell_style)],
        [Paragraph("HITL Escalation Rate", table_cell_bold), Paragraph("0.6250 (62.50%)", table_cell_style), Paragraph("Traps all 25 edge cases", table_cell_style)],
    ]

    t_base = Table(baseline_data, colWidths=[180, 140, 184])
    t_base.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ])
    )
    story.append(t_base)
    story.append(Spacer(1, 2))
    story.append(Paragraph("These values are baseline results for the shipped benchmark dataset and should be interpreted as an engineering benchmark.", body_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: RATIONALE, FUTURE SCOPE, REPRODUCIBILITY & GOVERNANCE
    # =========================================================================
    story.append(Paragraph("9. Why This Metric Set Was Chosen", h1_style))
    story.append(Paragraph("• <b>Safety:</b> Contradiction recall, confusion matrices, and cost-weighted error emphasize the asymmetric harm of corrupted borrower financials.", bullet_style))
    story.append(Paragraph("• <b>Class fairness:</b> balanced accuracy and macro metrics prevent payslip-heavy document distributions from hiding weak classification on rare deeds.", bullet_style))
    story.append(Paragraph("• <b>Extraction fidelity:</b> Exact Match, Token F1, and CER test whether granular entities and financial figures are extracted without distortion.", bullet_style))
    story.append(Paragraph("• <b>Trust in automation:</b> Brier, ECE, and reliability bins test whether confidence is reliable enough to support the 0.85 auto-processing threshold.", bullet_style))
    story.append(Paragraph("• <b>Operational health:</b> STP rate, gate triggers, and escalation rates expose document quality problems that static test sets cannot show in real time.", bullet_style))
    story.append(Paragraph("• <b>Auditability:</b> Provenance coverage guarantees full source verification rather than treating the LLM/OCR as an unverifiable authority.", bullet_style))

    story.append(Paragraph("10. Future Evaluation Scope", h1_style))
    story.append(Paragraph("• <b>Multilingual KYC extraction:</b> benchmark performance across Hindi, Tamil, Telugu, and Marathi regional identity documents.", bullet_style))
    story.append(Paragraph("• <b>Digital tampering detection:</b> quantify precision/recall on image splicing, font inconsistencies, and PDF metadata modifications.", bullet_style))
    story.append(Paragraph("• <b>Per-segment slicing:</b> evaluate performance by employer tier, income band, scan resolution, and bank statement format.", bullet_style))
    story.append(Paragraph("• <b>Latency and cost:</b> tokens, wall-clock time, and OCR compute cost per multi-page document bundle.", bullet_style))

    story.append(Paragraph("11. Implementation / Reproducibility", h1_style))
    story.append(Paragraph("The metrics can be reproduced using the project's evaluation CLI or API:", body_style))

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
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(t_cli)
    story.append(Spacer(1, 8))

    story.append(Paragraph("12. Scope and Governance Note", h1_style))
    story.append(
        Paragraph(
            "The Document Ingestion Agent is an evidentiary extraction and reconciliation component within a human-in-the-loop underwriting architecture. "
            "The metric framework is designed to evaluate engineering behavior, extraction fidelity, safety guardrails, calibration, and operational health. "
            "The prototype tolerance bands (±5%) and cost matrices are engineering choices; they should not be represented as official RBI rules or regulatory requirements.",
            body_style,
        )
    )

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated evaluation metrics PDF: '{output_filename}'")


if __name__ == "__main__":
    generate_pdf()
