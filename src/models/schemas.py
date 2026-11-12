from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    source_type: str = Field(..., description="'uploaded_document' or 'web_scraped'")
    filename: Optional[str] = None
    file_type: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    sheet: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    depth: Optional[int] = None
    domain: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: DocumentMetadata
    token_count: int = 0
    score: Optional[float] = None  # Similarity score when retrieved


class DiscoveredPage(BaseModel):
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    parent_url: Optional[str] = None
    depth: int = 0
    relevance_score: Optional[float] = None
    relevance_reason: Optional[str] = None
    selected: bool = False
    status: str = "discovered"  # discovered, evaluated, extracted, skipped, failed


class ScrapedPageContent(BaseModel):
    url: str
    title: str
    headings: List[str] = Field(default_factory=list)
    text: str
    cleaned_sections: List[Dict[str, str]] = Field(default_factory=list)
    extraction_method: str = "requests_bs4"  # requests_bs4 or js_rendering
    status_code: int = 200
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FilterDecision(BaseModel):
    url: str
    relevance_score: float = Field(..., description="Relevance score from 0.0 to 10.0")
    is_relevant: bool = Field(..., description="True if useful for research topic and instructions")
    reason: str = Field(..., description="Explanation of relevance or rejection reason")
    key_topics_found: List[str] = Field(default_factory=list)


class Citation(BaseModel):
    citation_id: int
    source_type: str  # "uploaded_document" or "web_evidence"
    source_label: str  # e.g., "Paper1.pdf (Page 4)" or "ArXiv Overview (https://...)"
    url_or_file: str
    page_or_section: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None


class SynthesisSection(BaseModel):
    title: str
    content: str
    citations: List[int] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    dimension: str
    uploaded_findings: str
    web_findings: str
    synthesis: str


class ResearchReport(BaseModel):
    title: str
    executive_summary: str
    instructions_applied: str
    sections: List[SynthesisSection] = Field(default_factory=list)
    comparison_table: Optional[List[ComparisonRow]] = None
    research_gaps: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

