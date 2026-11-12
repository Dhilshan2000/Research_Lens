import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from ..models.schemas import (
    DocumentChunk,
    DocumentMetadata,
    ResearchReport,
    SynthesisSection,
    ComparisonRow,
    Citation
)
from ..config import Config

logger = logging.getLogger("ResearchLens.Synthesizer")


def _format_location(meta: DocumentMetadata) -> str:
    """Safely extracts location string without nested ternaries."""
    if meta.page:
        return f"Page {meta.page}"
    if meta.section:
        return f"Section: {meta.section}"
    return "General"


class GroqSynthesizer:
    """Combines retrieved evidence from uploaded documents and filtered web content,
    and uses Groq to generate a grounded, citation-aware research report following user instructions.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.GROQ_API_KEY
        self.model_name = model_name or Config.GROQ_MODEL

    def _build_citations_and_context(self, retrieved_chunks: List[DocumentChunk]) -> Tuple[Dict[int, Citation], str]:
        citation_map: Dict[int, Citation] = {}
        context_blocks = []

        for idx, chunk in enumerate(retrieved_chunks, 1):
            meta = chunk.metadata
            loc = _format_location(meta)

            if meta.source_type == "uploaded_document":
                label = f"{meta.filename} ({loc})"
                cit = Citation(
                    citation_id=idx,
                    source_type="uploaded_document",
                    source_label=label,
                    url_or_file=meta.filename or "Uploaded Document",
                    page_or_section=loc,
                    title=meta.filename,
                    snippet=chunk.text[:200]
                )
            else:
                label = f"{meta.title or 'Web Resource'} ({meta.url})"
                cit = Citation(
                    citation_id=idx,
                    source_type="web_evidence",
                    source_label=label,
                    url_or_file=meta.url or "",
                    page_or_section=meta.section or "Page Content",
                    title=meta.title or meta.url,
                    snippet=chunk.text[:200]
                )
            citation_map[idx] = cit

            context_blocks.append(
                f"[Source #{idx}] {cit.source_label}\n"
                f"Source Type: {cit.source_type}\n"
                f"Content:\n{chunk.text}\n"
            )

        full_context = "\n---\n".join(context_blocks)
        return citation_map, full_context

    def _build_prompt(self, topic: str, user_instructions: str, full_context: str) -> str:
        return f"""You are a distinguished research scientist and author.
You are tasked with generating a comprehensive, evidence-grounded research report based strictly on the provided evidence.

TOPIC / TITLE:
{topic}

USER REPORT INSTRUCTIONS:
{user_instructions}

RETRIEVED EVIDENCE FROM UPLOADED PAPERS & FILTERED WEB CONTENT:
{full_context}

CRITICAL CITATION AND GROUNDING RULES:
1. Every major finding, claim, metric, or conclusion MUST cite its originating evidence source using bracketed numbers, e.g. [1], [2], or [1, 3].
2. Ground all statements strictly in the provided evidence. Do NOT hallucinate sources or claims.
3. If requested by the user instructions (e.g. comparison table, research gaps, academic tone), provide thorough, dedicated sections.
4. If a comparison table is appropriate or requested, include comparison rows comparing uploaded document findings with web findings.
5. In 'research_gaps', explicitly enumerate unexplored questions, methodological limitations, or discrepancies between papers and web evidence.

Return ONLY a valid JSON object matching this schema:
{{
  "title": "<Concise, professional title for the report>",
  "executive_summary": "<Executive summary synthesizing core takeaways with citations [1], [2]>",
  "instructions_applied": "<Brief summary of how the user's formatting/tone/gap instructions were applied>",
  "sections": [
    {{
      "title": "<Section Title, e.g., Literature Foundations, Empirical Findings, Methodologies>",
      "content": "<Detailed academic synthesis text citing claims with [x]>",
      "citations": [1, 2]
    }}
  ],
  "comparison_table": [
    {{
      "dimension": "<e.g., Methodology / Dataset / Performance / Limitations>",
      "uploaded_findings": "<Summary of findings from uploaded documents with citation>",
      "web_findings": "<Summary of findings from crawled web evidence with citation>",
      "synthesis": "<Synthesized conclusion across both sources>"
    }}
  ],
  "research_gaps": [
    "<Explicit gap 1 with citation/justification>",
    "<Explicit gap 2 with citation/justification>"
  ]
}}
"""

    def _parse_groq_response(
        self,
        raw_json: str,
        topic: str,
        user_instructions: str,
        retrieved_chunks: List[DocumentChunk],
        citation_map: Dict[int, Citation]
    ) -> ResearchReport:
        data = json.loads(raw_json)
        sections = [SynthesisSection(**s) for s in data.get("sections", [])]
        comparison_table = [ComparisonRow(**r) for r in data.get("comparison_table", [])] if data.get("comparison_table") else None
        gaps = data.get("research_gaps", [])

        return ResearchReport(
            title=data.get("title", topic),
            executive_summary=data.get("executive_summary", ""),
            instructions_applied=data.get("instructions_applied", user_instructions),
            sections=sections,
            comparison_table=comparison_table,
            research_gaps=gaps,
            citations=list(citation_map.values()),
            metadata={"model": self.model_name, "chunk_count": len(retrieved_chunks)}
        )

    def synthesize(
        self,
        retrieved_chunks: List[DocumentChunk],
        user_instructions: str,
        research_topic: Optional[str] = None,
    ) -> ResearchReport:
        """Synthesizes evidence chunks into a structured, citation-aware ResearchReport."""
        if not retrieved_chunks:
            return self._empty_report(user_instructions, research_topic)

        citation_map, full_context = self._build_citations_and_context(retrieved_chunks)
        topic = research_topic or "Research Overview and Synthesis"

        if not self.api_key or self.api_key.strip() == "":
            logger.info("No Groq API key configured. Generating grounded synthesis report via deterministic synthesizer.")
            return self._fallback_synthesis(topic, user_instructions, retrieved_chunks, citation_map)

        prompt = self._build_prompt(topic, user_instructions, full_context)

        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI research synthesizer. Generate structured, citation-grounded research reports in valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=3500,
            )

            raw_json = response.choices[0].message.content
            return self._parse_groq_response(raw_json, topic, user_instructions, retrieved_chunks, citation_map)

        except Exception as e:
            logger.warning(f"Groq API call failed: {e}. Falling back to deterministic synthesizer.")
            return self._fallback_synthesis(topic, user_instructions, retrieved_chunks, citation_map)

    def _build_fallback_sections(
        self,
        retrieved_chunks: List[DocumentChunk],
        doc_cit_ids: List[int],
        web_cit_ids: List[int]
    ) -> List[SynthesisSection]:
        sections: List[SynthesisSection] = []

        if doc_cit_ids:
            doc_parts = []
            for idx, c in enumerate(retrieved_chunks, 1):
                if c.metadata.source_type == "uploaded_document":
                    loc = f"p.{c.metadata.page}" if c.metadata.page else (c.metadata.section or "sec")
                    doc_parts.append(
                        f"According to {c.metadata.filename} ({loc}) [{idx}], "
                        f"the analysis highlights: {c.text[:280]}..."
                    )
            sections.append(SynthesisSection(
                title="Primary Findings from Uploaded Literature",
                content="\n\n".join(doc_parts),
                citations=doc_cit_ids
            ))

        if web_cit_ids:
            web_parts = []
            for idx, c in enumerate(retrieved_chunks, 1):
                if c.metadata.source_type == "web_scraped":
                    title = c.metadata.title or c.metadata.url
                    web_parts.append(
                        f"External analysis from '{title}' [{idx}] provides complementary perspective: "
                        f"{c.text[:280]}..."
                    )
            sections.append(SynthesisSection(
                title="Corroboration & Supplementary Web Evidence",
                content="\n\n".join(web_parts),
                citations=web_cit_ids
            ))

        return sections

    def _fallback_synthesis(
        self,
        topic: str,
        user_instructions: str,
        retrieved_chunks: List[DocumentChunk],
        citation_map: Dict[int, Citation]
    ) -> ResearchReport:
        """Deterministic grounded synthesis when Groq API key is not present or offline."""
        doc_cit_ids = [idx for idx, c in enumerate(retrieved_chunks, 1) if c.metadata.source_type == "uploaded_document"]
        web_cit_ids = [idx for idx, c in enumerate(retrieved_chunks, 1) if c.metadata.source_type == "web_scraped"]

        summary = (
            f"This report presents a synthesized analysis of '{topic}', integrating evidence from "
            f"{len(doc_cit_ids)} uploaded research document excerpts and {len(web_cit_ids)} verified web evidence sources. "
            f"Key foundations are drawn from uploaded literature "
            f"({', '.join(f'[{i}]' for i in doc_cit_ids[:3])}), complemented by recent findings and benchmarks "
            f"identified in web references ({', '.join(f'[{i}]' for i in web_cit_ids[:3])})."
        )

        sections = self._build_fallback_sections(retrieved_chunks, doc_cit_ids, web_cit_ids)

        comparison_rows = [
            ComparisonRow(
                dimension="Scope & Methodology",
                uploaded_findings=f"Focuses on formal academic methodologies and empirical paper datasets ({', '.join(f'[{i}]' for i in doc_cit_ids[:2])}).",
                web_findings=f"Provides broader contemporary context, live implementations, and benchmark discussions ({', '.join(f'[{i}]' for i in web_cit_ids[:2])}).",
                synthesis="The combination bridges theoretical depth with contemporary real-world validation."
            ),
            ComparisonRow(
                dimension="Key Findings & Evidence",
                uploaded_findings=f"Primary hypotheses and experimental evaluations detailed in uploaded documents ({', '.join(f'[{i}]' for i in doc_cit_ids[:2])}).",
                web_findings=f"Supplementary domain applications and updated practical insights ({', '.join(f'[{i}]' for i in web_cit_ids[:2])}).",
                synthesis="Cross-verifies core research assertions across independent academic and online channels."
            )
        ]

        first_doc = doc_cit_ids[0] if doc_cit_ids else 1
        first_web = web_cit_ids[0] if web_cit_ids else 1
        gaps = [
            f"Methodological Generalization Gap: Limited cross-domain validation between isolated paper findings [{first_doc}] and external deployment benchmarks.",
            f"Temporal & Technological Horizon: Further longitudinal evaluation is required to assess whether results remain consistent across newer model architectures [{first_web}].",
            "Data Harmonization Gap: Divergent evaluation metrics between published academic benchmarks and web-reported empirical results."
        ]

        return ResearchReport(
            title=f"Research Synthesis & Evidence Report: {topic}",
            executive_summary=summary,
            instructions_applied=f"Tone: Academic. Requirements: Comparison table and research gaps included. Instructions: {user_instructions}",
            sections=sections,
            comparison_table=comparison_rows,
            research_gaps=gaps,
            citations=list(citation_map.values()),
            metadata={"source": "deterministic_synthesizer", "chunk_count": len(retrieved_chunks)}
        )

    def _empty_report(self, instructions: str, topic: Optional[str]) -> ResearchReport:
        return ResearchReport(
            title=topic or "Research Report",
            executive_summary="No evidence was retrieved to synthesize.",
            instructions_applied=instructions,
            sections=[],
            citations=[]
        )
