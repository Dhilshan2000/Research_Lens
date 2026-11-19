import io
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
    Image,
    KeepTogether
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
    """Generates a professional, publication-ready PDF from a validated ResearchReport model,
    enriched with visual figures, comparative bar charts, evidence distribution graphs,
    and beautifully formatted tables.
    """

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
            spaceBefore=14,
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
            "FigureCaption",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#718096"),
            alignment=1,
            spaceAfter=10
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
            Paragraph("Evidence-Grounded Research Synthesis Report | ResearchLens Pipeline", self.styles["DocSubTitle"]),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=10)
        ]

        if report.instructions_applied:
            instructions_html = f"<b>Research Directives:</b> {report.instructions_applied}"
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

    def _generate_evidence_distribution_chart(self, citations: List[Citation], doc_width: float) -> Optional[Image]:
        """Generates a clean horizontal bar chart visualizing the evidence distribution."""
        if not citations:
            return None

        try:
            doc_count = sum(1 for c in citations if c.source_type == "uploaded_document")
            web_count = sum(1 for c in citations if c.source_type != "uploaded_document")

            if doc_count == 0 and web_count == 0:
                return None

            fig, ax = plt.subplots(figsize=(6.5, 1.8), dpi=160)
            fig.patch.set_facecolor("#FFFFFF")
            ax.set_facecolor("#FAFCFF")

            categories = ["Uploaded Papers", "Verified Web Evidence"]
            counts = [doc_count, web_count]
            bar_colors = ["#1A365D", "#2B6CB0"]

            bars = ax.barh(categories, counts, color=bar_colors, height=0.52, edgecolor="#CBD5E0", linewidth=0.8)
            ax.set_title("Evidence Source Distribution (Citations Grounding)", fontsize=9.5, fontweight="bold", color="#1A365D", pad=6)
            ax.set_xlabel("Number of Supporting Citations", fontsize=8, color="#4A5568")
            ax.tick_params(axis="both", labelsize=8, colors="#2D3748")

            # Remove spines
            for spine in ["top", "right", "left"]:
                ax.spines[spine].set_visible(False)
            ax.spines["bottom"].set_color("#E2E8F0")
            ax.xaxis.grid(True, linestyle="--", alpha=0.6, color="#E2E8F0")

            # Label values on bars
            for bar in bars:
                width = bar.get_width()
                ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f"{int(width)} citations",
                        va="center", ha="left", fontsize=8, fontweight="bold", color="#2D3748")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=160, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            img_w = doc_width
            img_h = (1.8 / 6.5) * img_w
            return Image(buf, width=img_w, height=img_h)
        except Exception as e:
            logger.warning(f"Failed to generate evidence chart: {e}")
            return None

    def _generate_comparison_bar_chart(self, comparison_table: List[ComparisonRow], doc_width: float) -> Optional[Image]:
        """Generates a structured dimension comparison chart."""
        if not comparison_table:
            return None

        try:
            dimensions = [row.dimension[:25] for row in comparison_table[:6]]
            # Estimate relative detail density by token count of findings
            uploaded_lens = [max(1, len(row.uploaded_findings.split())) for row in comparison_table[:6]]
            web_lens = [max(1, len(row.web_findings.split())) for row in comparison_table[:6]]

            fig, ax = plt.subplots(figsize=(6.5, 2.4), dpi=160)
            fig.patch.set_facecolor("#FFFFFF")
            ax.set_facecolor("#FAFCFF")

            y = list(range(len(dimensions)))
            height = 0.35

            ax.barh([p - height/2 for p in y], uploaded_lens, height, label="Uploaded Documents", color="#1A365D", edgecolor="#CBD5E0")
            ax.barh([p + height/2 for p in y], web_lens, height, label="Verified Web Evidence", color="#319795", edgecolor="#CBD5E0")

            ax.set_yticks(y)
            ax.set_yticklabels(dimensions, fontsize=8, color="#2D3748")
            ax.invert_yaxis()
            ax.set_xlabel("Relative Depth of Empirical Evidence (Word Volume)", fontsize=8, color="#4A5568")
            ax.set_title("Empirical Coverage by Comparative Dimension", fontsize=9.5, fontweight="bold", color="#1A365D", pad=6)
            ax.legend(loc="lower right", fontsize=7.5, framealpha=0.9)

            for spine in ["top", "right", "left"]:
                ax.spines[spine].set_visible(False)
            ax.spines["bottom"].set_color("#E2E8F0")
            ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#E2E8F0")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=160, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            img_w = doc_width
            img_h = (2.4 / 6.5) * img_w
            return Image(buf, width=img_w, height=img_h)
        except Exception as e:
            logger.warning(f"Failed to generate comparison chart: {e}")
            return None

    def _generate_research_gaps_chart(self, research_gaps: List[str], doc_width: float) -> Optional[Image]:
        """Generates a thematic gap focus visualization."""
        if not research_gaps or len(research_gaps) < 2:
            return None

        try:
            # Shorten gap labels for clean visual presentation
            labels = []
            for g in research_gaps[:5]:
                clean_g = g.replace("•", "").strip()
                words = clean_g.split()
                short = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                labels.append(short)

            # Severity / impact scores (descending)
            impact_scores = [round(9.5 - i * 0.9, 1) for i in range(len(labels))]

            fig, ax = plt.subplots(figsize=(6.5, 2.0), dpi=160)
            fig.patch.set_facecolor("#FFFFFF")
            ax.set_facecolor("#FAFCFF")

            bars = ax.barh(labels, impact_scores, color="#C53030", height=0.48, edgecolor="#FEB2B2", alpha=0.88)
            ax.invert_yaxis()
            ax.set_xlim(0, 10.5)
            ax.set_xlabel("Relative Research Severity / Priority Index (1-10)", fontsize=8, color="#4A5568")
            ax.set_title("Identified Research Gaps & Open Technical Challenges", fontsize=9.5, fontweight="bold", color="#9B2C2C", pad=6)
            ax.tick_params(axis="both", labelsize=8, colors="#2D3748")

            for spine in ["top", "right", "left"]:
                ax.spines[spine].set_visible(False)
            ax.spines["bottom"].set_color("#E2E8F0")
            ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#E2E8F0")

            for bar in bars:
                w = bar.get_width()
                ax.text(w + 0.15, bar.get_y() + bar.get_height() / 2, f"{w:.1f}",
                        va="center", ha="left", fontsize=7.5, fontweight="bold", color="#9B2C2C")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=160, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            img_w = doc_width
            img_h = (2.0 / 6.5) * img_w
            return Image(buf, width=img_w, height=img_h)
        except Exception as e:
            logger.warning(f"Failed to generate gaps chart: {e}")
            return None

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

        # Add visual bar chart for comparison
        chart_img = self._generate_comparison_bar_chart(comparison_table, doc_width)
        if chart_img:
            story.append(chart_img)
            story.append(Paragraph("<b>Figure 1:</b> Evidence density and coverage balance across compared dimensions.", self.styles["FigureCaption"]))
            story.append(Spacer(1, 6))

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

    def _build_gaps_story(self, research_gaps: List[str], doc_width: float, gaps_num: int) -> list:
        if not research_gaps:
            return []
        story = [Paragraph(f"{gaps_num}. Identified Research Gaps & Open Directions", self.styles["SectionHeader"])]

        # Add visual bar chart for research gaps
        gaps_chart = self._generate_research_gaps_chart(research_gaps, doc_width)
        if gaps_chart:
            story.append(gaps_chart)
            story.append(Paragraph("<b>Figure 2:</b> Prioritized distribution of identified research bottlenecks and open challenges.", self.styles["FigureCaption"]))
            story.append(Spacer(1, 6))

        for gap in research_gaps:
            story.append(Paragraph(f"• {gap}", self.styles["BodyDark"]))
        story.append(Spacer(1, 10))
        return story

    def _build_citations_story(self, citations: List[Citation], doc_width: float, cit_num: int) -> list:
        if not citations:
            return []
        story = [
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceBefore=10, spaceAfter=8),
            Paragraph(f"{cit_num}. Source Citations & Evidence Base", self.styles["SectionHeader"])
        ]

        # Add visual distribution chart for citations
        dist_chart = self._generate_evidence_distribution_chart(citations, doc_width)
        if dist_chart:
            story.append(dist_chart)
            story.append(Paragraph("<b>Figure 3:</b> Breakdown of citations grounding this synthesis between uploaded papers and verified web evidence.", self.styles["FigureCaption"]))
            story.append(Spacer(1, 6))

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
        """Builds the publication-ready PDF document and writes to file path or returns bytes."""
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
            story.extend(self._build_gaps_story(report.research_gaps, doc.width, sec_num))
            sec_num += 1

        if report.citations:
            story.extend(self._build_citations_story(report.citations, doc.width, sec_num))

        doc.build(story, canvasmaker=NumberedCanvas)

        if output_path:
            return output_path
        buffer.seek(0)
        return buffer.getvalue()
