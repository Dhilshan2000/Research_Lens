import re
import uuid
import logging
from typing import List, Dict, Any, Optional

from ..models.schemas import DocumentChunk, DocumentMetadata, ScrapedPageContent
from ..parsers.document_parser import ParsedDocumentItem
from ..config import Config

logger = logging.getLogger("ResearchLens.Chunker")


class DocumentChunker:
    """Chunks text into windows of ~500-800 tokens with 10-20% overlap,
    while strictly retaining all source metadata for citations and grounding.
    """

    def __init__(
        self,
        chunk_size: int = Config.CHUNK_SIZE,
        chunk_overlap: int = Config.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._tokenizer = None

    def _get_tokenizer(self):
        if self._tokenizer is None:
            try:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer = "fallback"
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        tokenizer = self._get_tokenizer()
        if tokenizer != "fallback" and hasattr(tokenizer, "encode"):
            try:
                return len(tokenizer.encode(text))
            except Exception:
                pass
        # Fallback word-based estimation (~1 token ~= 0.75 words, or 1 token ~= 4 chars)
        return max(1, len(text.split()) * 4 // 3)

    def _split_into_token_chunks(self, text: str) -> List[str]:
        """Splits raw text into chunks respecting chunk_size and chunk_overlap."""
        text = text.strip()
        if not text:
            return []

        tokenizer = self._get_tokenizer()
        if tokenizer != "fallback" and hasattr(tokenizer, "encode") and hasattr(tokenizer, "decode"):
            try:
                tokens = tokenizer.encode(text)
                if len(tokens) <= self.chunk_size:
                    return [text]

                chunks = []
                step = self.chunk_size - self.chunk_overlap
                for i in range(0, len(tokens), step):
                    token_slice = tokens[i:i + self.chunk_size]
                    chunk_text = tokenizer.decode(token_slice).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    if i + self.chunk_size >= len(tokens):
                        break
                return chunks
            except Exception as e:
                logger.debug(f"Tiktoken encoding failed: {e}. Falling back to paragraph/word split.")

        # Paragraph and word based fallback
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_tokens = 0

        for p in paragraphs:
            p_tokens = self.count_tokens(p)
            if current_tokens + p_tokens <= self.chunk_size:
                current_chunk.append(p)
                current_tokens += p_tokens
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    # Keep some overlap paragraphs if possible
                    overlap_tokens = 0
                    overlap_paras = []
                    for op in reversed(current_chunk):
                        op_tok = self.count_tokens(op)
                        if overlap_tokens + op_tok <= self.chunk_overlap:
                            overlap_paras.insert(0, op)
                            overlap_tokens += op_tok
                        else:
                            break
                    current_chunk = overlap_paras + [p]
                    current_tokens = overlap_tokens + p_tokens
                else:
                    # Single very long paragraph: break by words
                    words = p.split()
                    step = max(1, self.chunk_size - self.chunk_overlap)
                    for w_idx in range(0, len(words), step):
                        slice_words = words[w_idx:w_idx + self.chunk_size]
                        chunks.append(" ".join(slice_words))
                    current_chunk = []
                    current_tokens = 0

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def chunk_document_items(self, parsed_items: List[ParsedDocumentItem]) -> List[DocumentChunk]:
        """Chunks parsed research document items (PDF, DOCX, TXT, CSV, XLSX)."""
        chunks: List[DocumentChunk] = []

        for item_idx, item in enumerate(parsed_items):
            text_chunks = self._split_into_token_chunks(item.text)
            for c_idx, text_chunk in enumerate(text_chunks):
                chunk_id = f"doc_{item.filename}_p{item.page or 1}_s{item_idx}_c{c_idx}_{uuid.uuid4().hex[:6]}"
                metadata = DocumentMetadata(
                    source_type="uploaded_document",
                    filename=item.filename,
                    file_type=item.file_type,
                    page=item.page,
                    section=item.section,
                    sheet=item.sheet,
                    title=item.filename,
                    extra={
                        "total_pages": item.total_pages,
                        **item.extra_metadata
                    }
                )
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    text=text_chunk,
                    metadata=metadata,
                    token_count=self.count_tokens(text_chunk)
                ))

        return chunks

    def chunk_scraped_pages(self, scraped_pages: List[ScrapedPageContent]) -> List[DocumentChunk]:
        """Chunks extracted web page content with web source metadata."""
        chunks: List[DocumentChunk] = []

        for p_idx, page in enumerate(scraped_pages):
            # Chunk each cleaned section or full page text
            if page.cleaned_sections:
                for s_idx, sec in enumerate(page.cleaned_sections):
                    heading = sec.get("heading", "Section")
                    content = sec.get("content", "")
                    sec_text = f"### {heading}\n{content}"
                    text_chunks = self._split_into_token_chunks(sec_text)

                    for c_idx, text_chunk in enumerate(text_chunks):
                        chunk_id = f"web_{p_idx}_s{s_idx}_c{c_idx}_{uuid.uuid4().hex[:6]}"
                        metadata = DocumentMetadata(
                            source_type="web_scraped",
                            url=page.url,
                            title=page.title,
                            section=heading,
                            domain=page.metadata.get("domain", ""),
                            extra={"extraction_method": page.extraction_method}
                        )
                        chunks.append(DocumentChunk(
                            chunk_id=chunk_id,
                            text=text_chunk,
                            metadata=metadata,
                            token_count=self.count_tokens(text_chunk)
                        ))
            else:
                text_chunks = self._split_into_token_chunks(page.text)
                for c_idx, text_chunk in enumerate(text_chunks):
                    chunk_id = f"web_{p_idx}_c{c_idx}_{uuid.uuid4().hex[:6]}"
                    metadata = DocumentMetadata(
                        source_type="web_scraped",
                        url=page.url,
                        title=page.title,
                        domain=page.metadata.get("domain", ""),
                        extra={"extraction_method": page.extraction_method}
                    )
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_id,
                        text=text_chunk,
                        metadata=metadata,
                        token_count=self.count_tokens(text_chunk)
                    ))

        return chunks

