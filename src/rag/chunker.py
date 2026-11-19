import re
import uuid
import logging
from typing import List, Dict, Any, Optional

from ..models.schemas import DocumentChunk, DocumentMetadata, ScrapedPageContent
from ..parsers.document_parser import ParsedDocumentItem
from ..config import Config

logger = logging.getLogger("ResearchLens.Chunker")


class DocumentChunker:
    """Meaningful, sentence-aware chunker that preserves complete words, grammatical sentences,
    and structural headings using NLTK sentence tokenization with recursive boundary fallback.
    Prevents splitting through words or mid-sentence fragmentation.
    """

    def __init__(
        self,
        chunk_size: int = Config.CHUNK_SIZE,
        chunk_overlap: int = Config.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._tokenizer = None
        self._nltk_available = False
        self._spacy_nlp = None
        self._init_sentence_splitters()

    def _init_sentence_splitters(self):
        """Initializes NLTK or spaCy sentence tokenizers."""
        try:
            import nltk
            # Ensure punkt / punkt_tab is loaded
            try:
                nltk.data.find("tokenizers/punkt")
                self._nltk_available = True
            except LookupError:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)
                self._nltk_available = True
        except Exception:
            self._nltk_available = False

        try:
            import spacy
            self._spacy_nlp = spacy.blank("en")
            self._spacy_nlp.add_pipe("sentencizer")
        except Exception:
            self._spacy_nlp = None

    def _get_tokenizer(self):
        if self._tokenizer is None:
            try:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer = "fallback"
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """Accurately counts tokens via tiktoken or falls back to word-length estimation."""
        if not text:
            return 0
        tokenizer = self._get_tokenizer()
        if tokenizer != "fallback" and hasattr(tokenizer, "encode"):
            try:
                return len(tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text.split()) * 4 // 3)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits paragraph text into complete grammatical sentences."""
        text = text.strip()
        if not text:
            return []

        # 1. Try spaCy if present
        if self._spacy_nlp is not None:
            try:
                doc = self._spacy_nlp(text)
                sents = [s.text.strip() for s in doc.sents if s.text.strip()]
                if sents:
                    return sents
            except Exception:
                pass

        # 2. Try NLTK sent_tokenize
        if self._nltk_available:
            try:
                import nltk
                sents = nltk.sent_tokenize(text)
                clean_sents = [s.strip() for s in sents if s.strip()]
                if clean_sents:
                    return clean_sents
            except Exception:
                pass

        # 3. Robust Regex Sentence Splitter fallback
        # Splits on period, question mark, or exclamation mark followed by whitespace and capital letter
        raw_sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'‘“])", text)
        return [s.strip() for s in raw_sents if s.strip()]

    def _split_long_sentence_into_words(self, sentence: str, max_tokens: int) -> List[str]:
        """Splits an oversized single sentence strictly on whitespace word boundaries.
        Guarantees that words are NEVER sliced in half.
        """
        words = sentence.split()
        if not words:
            return []

        slices = []
        current_words = []
        current_tokens = 0

        for w in words:
            w_tokens = self.count_tokens(w + " ")
            if current_tokens + w_tokens <= max_tokens:
                current_words.append(w)
                current_tokens += w_tokens
            else:
                if current_words:
                    slices.append(" ".join(current_words))
                    current_words = [w]
                    current_tokens = w_tokens
                else:
                    # Single extremely long word token (e.g. giant base64 or URL)
                    slices.append(w)
                    current_words = []
                    current_tokens = 0

        if current_words:
            slices.append(" ".join(current_words))

        return slices

    def _split_into_meaningful_chunks(self, text: str) -> List[str]:
        """Performs hierarchical sentence-aware chunking:
        1. Breaks by paragraphs/sections to respect document flow.
        2. Segments into full sentences.
        3. Packs sentences until chunk_size is reached.
        4. Overlaps using complete sentences (never slicing words).
        """
        text = text.strip()
        if not text:
            return []

        # If text is already under chunk limit, return directly
        if self.count_tokens(text) <= self.chunk_size:
            return [text]

        # Break text into paragraphs first (respect markdown headings and double newlines)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        
        # Flatten into a stream of logical sentences
        sentences: List[str] = []
        for p in paragraphs:
            # Check if paragraph is a markdown header
            if p.startswith("#") or (len(p) < 80 and p.isupper()):
                sentences.append(p)
            else:
                p_sents = self._split_into_sentences(p)
                for s in p_sents:
                    if self.count_tokens(s) > self.chunk_size:
                        # Break massive single sentence by whole words
                        sentences.extend(self._split_long_sentence_into_words(s, self.chunk_size))
                    else:
                        sentences.append(s)

        if not sentences:
            return []

        chunks: List[str] = []
        current_chunk_sents: List[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = self.count_tokens(sent)

            if current_tokens + sent_tokens <= self.chunk_size:
                current_chunk_sents.append(sent)
                current_tokens += sent_tokens
            else:
                # Flush current chunk
                if current_chunk_sents:
                    chunk_str = " ".join(current_chunk_sents).strip()
                    if chunk_str:
                        chunks.append(chunk_str)

                    # Compute overlap using whole sentences
                    overlap_tokens = 0
                    overlap_sents: List[str] = []
                    for prev_sent in reversed(current_chunk_sents):
                        p_tok = self.count_tokens(prev_sent)
                        if overlap_tokens + p_tok <= self.chunk_overlap:
                            overlap_sents.insert(0, prev_sent)
                            overlap_tokens += p_tok
                        else:
                            break

                    current_chunk_sents = overlap_sents + [sent]
                    current_tokens = overlap_tokens + sent_tokens
                else:
                    # Single sentence fit
                    chunks.append(sent)
                    current_chunk_sents = []
                    current_tokens = 0

        if current_chunk_sents:
            final_str = " ".join(current_chunk_sents).strip()
            if final_str and (not chunks or final_str != chunks[-1]):
                chunks.append(final_str)

        return chunks

    def chunk_document_items(self, parsed_items: List[ParsedDocumentItem]) -> List[DocumentChunk]:
        """Chunks parsed research document items (PDF, DOCX, TXT, CSV, XLSX)
        while preserving all citation and source metadata.
        """
        chunks: List[DocumentChunk] = []

        for item_idx, item in enumerate(parsed_items):
            text_chunks = self._split_into_meaningful_chunks(item.text)
            for c_idx, text_chunk in enumerate(text_chunks):
                # Avoid trivial or empty chunks (< 10 characters)
                if len(text_chunk.strip()) < 10:
                    continue

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
            if page.cleaned_sections:
                for s_idx, sec in enumerate(page.cleaned_sections):
                    heading = sec.get("heading", "Section")
                    content = sec.get("content", "")
                    sec_text = f"### {heading}\n{content}"
                    text_chunks = self._split_into_meaningful_chunks(sec_text)

                    for c_idx, text_chunk in enumerate(text_chunks):
                        if len(text_chunk.strip()) < 10:
                            continue

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
                text_chunks = self._split_into_meaningful_chunks(page.text)
                for c_idx, text_chunk in enumerate(text_chunks):
                    if len(text_chunk.strip()) < 10:
                        continue

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
