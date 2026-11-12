import io
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfgen import canvas

from ..models.schemas import ResearchReport, SynthesisSection, ComparisonRow, Citation
from ..config import Config

logger = logging.getLogger("ResearchLens.PDFGenerator")


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page count (Page X of Y)
    along with running header and footer.
    """

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
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "ResearchLens — Grounded RAG Research Report")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.drawString(54, 30, f"Generated: {date_str} | Evidence-grounded synthesis")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 30, page_str)

        self.restoreState()


class PDFReportGenerator:
    """Generates a professional, citation-aware PDF from a validated ResearchReport model."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        primary_color = colors.HexColor("#1A365D")   # Deep Navy
        text_dark = colors.HexColor("#2D3748")       # Charcoal

        self.styles.add(ParagraphStyle(
            "DocTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=primary_color,
            spaceAfter=6
        ))

        self.styles.add(ParagraphStyle(
            "DocSubTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=12
        ))

        self.styles.add(ParagraphStyle(
            "SectionHeader",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=primary_color,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        ))

        self.styles.add(ParagraphStyle(
            "BodyDark",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=text_dark,
            spaceAfter=8
        ))

        self.styles.add(ParagraphStyle(
            "CalloutText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#2C5282")
        ))

        self.styles.add(ParagraphStyle(
            "TableHeader",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
            alignment=1
        ))

        self.styles.add(ParagraphStyle(
            "TableCell",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=text_dark
        ))

        self.styles.add(ParagraphStyle(
            "CitationItem",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=4
        ))

    def _build_header_story(self, report: ResearchReport, doc_width: float) -> list:
        story = [
            Paragraph(report.title, self.styles["DocTitle"]),
            Paragraph("Evidence-Grounded Research Synthesis Report | ResearchLens RAG Pipeline", self.styles["DocSubTitle"]),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=10)
        ]

        if report.instructions_applied:
            instructions_html = f"<b>Report Directives:</b> {report.instructions_applied}"
            callout_data = [[Paragraph(instructions_html, self.styles["CalloutText"])]]
            callout_table = Table(callout_data, colWidths=[doc_width])
            callout_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
                ("BORDER", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([callout_table, Spacer(1, 10)])

        return story

    def _build_summary_story(self, summary: str) -> list:
        if not summary:
            return []
        return [
            Paragraph("1. Executive Summary", self.styles["SectionHeader"]),
            Paragraph(summary, self.styles["BodyDark"]),
            Spacer(1, 8)
        ]

    def _build_sections_story(self, sections: List[SynthesisSection]) -> list:
        story = []
        for idx, sec in enumerate(sections, 2):
            story.append(Paragraph(f"{idx}. {sec.title}", self.styles["SectionHeader"]))
            for p in sec.content.split("\n\n"):
                p_clean = p.strip()
                if p_clean:
                    story.append(Paragraph(p_clean, self.styles["BodyDark"]))
            story.append(Spacer(1, 8))
        return story

    def _build_comparison_table_story(self, comparison_table: List[ComparisonRow], doc_width: float, sec_num: int) -> list:
        if not comparison_table:
            return []

        story = [Paragraph(f"{sec_num}. Comparative Evidence Synthesis", self.styles["SectionHeader"])]
        table_data = [[
            Paragraph("<b>Dimension / Focus</b>", self.styles["TableHeader"]),
            Paragraph("<b>Uploaded Document Findings</b>", self.styles["TableHeader"]),
            Paragraph("<b>Filtered Web Evidence</b>", self.styles["TableHeader"]),
            Paragraph("<b>Synthesized Conclusion</b>", self.styles["TableHeader"]),
        ]]
        col_widths = [doc_width * 0.20, doc_width * 0.28, doc_width * 0.28, doc_width * 0.24]

        for row in comparison_table:
            table_data.append([
                Paragraph(row.dimension, self.styles["TableCell"]),
                Paragraph(row.uploaded_findings, self.styles["TableCell"]),
                Paragraph(row.web_findings, self.styles["TableCell"]),
                Paragraph(row.synthesis, self.styles["TableCell"]),
            ])

        comp_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        comp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([comp_table, Spacer(1, 10)])
        return story

    def _build_gaps_story(self, research_gaps: List[str], gaps_num: int) -> list:
        if not research_gaps:
            return []
        story = [Paragraph(f"{gaps_num}. Identified Research Gaps & Open Directions", self.styles["SectionHeader"])]
        for gap in research_gaps:
            story.append(Paragraph(f"• {gap}", self.styles["BodyDark"]))
        story.append(Spacer(1, 10))
        return story

    def _build_citations_story(self, citations: List[Citation], cit_num: int) -> list:
        if not citations:
            return []
        story = [
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceBefore=10, spaceAfter=8),
            Paragraph(f"{cit_num}. Source Citations & Evidence Base", self.styles["SectionHeader"])
        ]
        for cit in citations:
            prefix = f"<b>[{cit.citation_id}]</b>"
            if cit.source_type == "uploaded_document":
                loc = cit.page_or_section or "N/A"
                desc = f"{prefix} <i>[Uploaded Research File]</i> <b>{cit.url_or_file}</b> | Location: {loc}"
            else:
                desc = f"{prefix} <i>[Verified Web Evidence]</i> <b>{cit.title}</b> | URL: <u>{cit.url_or_file}</u>"

            if cit.snippet:
                desc += f"<br/>&nbsp;&nbsp;&nbsp;&nbsp;<font color='#718096'>Excerpt: \"{cit.snippet.strip()}\"</font>"

            story.append(Paragraph(desc, self.styles["CitationItem"]))
        return story

    def generate_pdf(self, report: ResearchReport, output_path: str | None = None) -> str | bytes:
        """Builds the PDF document and writes to file path or returns bytes."""
        buffer = io.BytesIO()
        target = output_path or buffer

        doc = SimpleDocTemplate(
            target,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        story = []
        story.extend(self._build_header_story(report, doc.width))
        story.extend(self._build_summary_story(report.executive_summary))
        story.extend(self._build_sections_story(report.sections))

        sec_num = len(report.sections) + 2
        if report.comparison_table:
            story.extend(self._build_comparison_table_story(report.comparison_table, doc.width, sec_num))
            sec_num += 1

        if report.research_gaps:
            story.extend(self._build_gaps_story(report.research_gaps, sec_num))
            sec_num += 1

        if report.citations:
            story.extend(self._build_citations_story(report.citations, sec_num))

        doc.build(story, canvasmaker=NumberedCanvas)

        if output_path:
            return output_path
        buffer.seek(0)
        return buffer.getvalue()
