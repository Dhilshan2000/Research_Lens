import os
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import streamlit as st

# Add workspace directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import Config
from src.parsers.document_parser import DocumentParser, ParsedDocumentItem
from src.scraper.crawler import BoundedCrawler
from src.scraper.state_machine import ScrapingStateMachine, CrawlState
from src.filter.relevance_filter import RelevanceFilter
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingEngine
from src.rag.vector_store import VectorStore
from src.synthesizer.groq_synthesizer import GroqSynthesizer
from src.exporter.pdf_generator import PDFReportGenerator
from src.models.schemas import ResearchReport, DiscoveredPage, DocumentChunk

# Page Configuration
st.set_page_config(
    page_title="ResearchLens — RAG Research Paper Summarizer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "report" not in st.session_state:
    st.session_state.report = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "discovered_pages" not in st.session_state:
    st.session_state.discovered_pages = []
if "retrieved_chunks" not in st.session_state:
    st.session_state.retrieved_chunks = []
if "all_chunks" not in st.session_state:
    st.session_state.all_chunks = []
if "ingested_files_info" not in st.session_state:
    st.session_state.ingested_files_info = []

# Sidebar Configuration
with st.sidebar:
    st.title("⚙️ System Settings")
    st.markdown("Configure LLM, crawler, and RAG retrieval parameters.")

    if Config.GROQ_API_KEY:
        st.success("🔑 Groq API Key: Configured in `.env`")
    else:
        st.info("ℹ️ Groq API Key: Not set in `.env` (Deterministic mode active)")

    model_options = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]
    default_index = model_options.index(Config.GROQ_MODEL) if Config.GROQ_MODEL in model_options else 0
    groq_model = st.selectbox(
        "Synthesis LLM Model",
        options=model_options,
        index=default_index,
        help="Groq instruction model for synthesis report generation."
    )

    st.markdown("---")
    st.subheader("🕸️ Crawler & Filter Controls")
    crawl_depth = st.slider("Max Crawl Depth", min_value=1, max_value=3, value=1, help="Depth 1 crawls seed URLs and direct links.")
    max_pages = st.slider("Max Discovered Pages", min_value=5, max_value=25, value=12, help="Upper bound on discovered pages per session.")
    same_domain = st.checkbox("Strict Same Domain", value=True, help="Restrict crawling to the domains of the seed URLs.")
    relevance_threshold = st.slider("LLM Filter Threshold", min_value=1.0, max_value=10.0, value=6.0, step=0.5, help="Minimum score (0-10) for candidate pages to be extracted.")

    st.markdown("---")
    st.subheader("🔍 RAG & Chunking Controls")
    top_k = st.slider("Top-K Retrieved Chunks", min_value=3, max_value=10, value=5, help="Number of evidence chunks passed to the LLM.")
    chunk_size = st.slider("Chunk Size (Tokens)", min_value=300, max_value=900, value=600, step=50)
    chunk_overlap = st.slider("Chunk Overlap (Tokens)", min_value=50, max_value=200, value=100, step=25)


# Header
st.title("🔬 ResearchLens")
st.markdown(
    "**RAG Research Paper Summarization Tool** — Integrates uploaded research papers "
    "(PDF, DOCX, TXT, CSV, XLSX) with bounded, LLM-filtered web evidence into a citation-grounded synthesis report."
)
st.markdown("---")

# Main Input Section
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Upload Research Material")
    uploaded_files = st.file_uploader(
        "Upload papers (PDF, DOCX, TXT) and supplementary data (CSV, XLSX)",
        type=["pdf", "docx", "txt", "csv", "xlsx"],
        accept_multiple_files=True,
        help="Accepts multiple research papers and tabular datasets in one session."
    )
    if uploaded_files:
        st.caption(f"📁 {len(uploaded_files)} file(s) selected:")
        for uf in uploaded_files:
            st.text(f"  • {uf.name} ({round(uf.size / 1024, 1)} KB)")

    st.subheader("2. Reference URLs (Bounded Crawl)")
    seed_urls_input = st.text_area(
        "Enter crawl starting URLs (one per line):",
        value="https://arxiv.org/abs/2312.10997",
        height=100,
        help="Bounded crawler starts exclusively from these URLs, discovers candidate links, and uses the LLM filter to extract relevant web evidence."
    )

with col2:
    st.subheader("3. Document Instructions & Focus")
    research_topic = st.text_input(
        "Research Topic / Subject:",
        value="Retrieval-Augmented Generation (RAG) Architecture and Gaps",
        help="The core research theme used for filtering web evidence and organizing the synthesis report."
    )

    preset = st.selectbox(
        "Instruction Presets:",
        options=[
            "Standard Brief (Academic tone, research gaps, comparison table, under 4 pages)",
            "Literature Review & Methodological Analysis",
            "Executive Briefing & Strategic Gaps",
            "Custom Directives"
        ],
        index=0
    )

    preset_texts = {
        "Standard Brief (Academic tone, research gaps, comparison table, under 4 pages)": (
            "Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages. "
            "Critically analyze the methodology, empirical results, and contrast the uploaded findings with recent external web evidence."
        ),
        "Literature Review & Methodological Analysis": (
            "Provide a rigorous comparative literature review. Focus on algorithm design, experimental datasets, benchmark evaluations, "
            "and contrast theoretical claims from the uploaded papers against real-world web implementations. Include a comparison table."
        ),
        "Executive Briefing & Strategic Gaps": (
            "Deliver an executive briefing summarizing business implications, architectural trade-offs, and critical gaps in adoption. "
            "Maintain a formal professional tone, highlight key bottlenecks, and construct a synthesis comparison matrix."
        ),
        "Custom Directives": ""
    }

    default_instruction = preset_texts.get(preset, "")
    user_instructions = st.text_area(
        "Report Directives & Instructions:",
        value=default_instruction if preset != "Custom Directives" else "",
        placeholder="e.g. Focus on research gaps, use an academic tone, add a comparison table...",
        height=140
    )

st.markdown("---")

# Execution Button
run_pipeline = st.button("🚀 Run ResearchLens Pipeline", type="primary", use_container_width=True)

if run_pipeline:
    if not uploaded_files and not seed_urls_input.strip():
        st.error("Please provide at least one uploaded research file or reference URL.")
        st.stop()

    if not user_instructions.strip():
        user_instructions = "Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages."

    progress_bar = st.progress(0)
    status_box = st.empty()

    # Step 1: Parse Uploaded Documents
    status_box.info("📑 Step 1/6: Ingesting and parsing uploaded research materials...")
    parsed_items: List[ParsedDocumentItem] = []
    ingested_info = []

    if uploaded_files:
        for uf in uploaded_files:
            # Save to temporary file for parser
            suffix = Path(uf.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uf.getvalue())
                tmp_path = tmp_file.name

            try:
                items = DocumentParser.parse_file(tmp_path, original_filename=uf.name)
                parsed_items.extend(items)
                ingested_info.append({
                    "filename": uf.name,
                    "type": suffix.lstrip("."),
                    "items_count": len(items),
                    "total_chars": sum(len(it.text) for it in items)
                })
            except Exception as e:
                st.warning(f"Error parsing file '{uf.name}': {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    st.session_state.ingested_files_info = ingested_info
    progress_bar.progress(20)

    # Step 2: Bounded Crawling & Discovery
    seed_urls = [u.strip() for u in seed_urls_input.splitlines() if u.strip()]
    discovered_candidates: List[DiscoveredPage] = []
    scraped_pages = []

    if seed_urls:
        status_box.info("🕸️ Step 2/6: Performing bounded crawling & candidate link discovery...")
        crawler = BoundedCrawler(
            max_depth=crawl_depth,
            max_pages=max_pages,
            same_domain_only=same_domain,
            progress_callback=lambda msg, cur, tot: status_box.text(f"🕸️ {msg}")
        )
        discovered_candidates = crawler.discover_candidates(seed_urls)
        progress_bar.progress(40)

        # Step 3: LLM Relevance Filtering
        status_box.info("🤖 Step 3/6: Running LLM Relevance Filter on candidate pages...")
        rel_filter = RelevanceFilter(
            api_key=Config.GROQ_API_KEY,
            model_name=Config.GROQ_FILTER_MODEL,
            threshold=relevance_threshold
        )
        selected_pages = rel_filter.evaluate_candidates(
            discovered_candidates,
            user_instructions=user_instructions,
            research_topic=research_topic
        )
        st.session_state.discovered_pages = discovered_candidates
        progress_bar.progress(55)

        # Step 4: Full Content Extraction for Selected Pages
        status_box.info(f"📥 Step 4/6: Extracting and cleaning content from {len(selected_pages)} approved web pages...")
        scraped_pages = crawler.extract_selected(selected_pages)
        progress_bar.progress(70)

    # Step 5: Chunking & Vector Indexing
    status_box.info("🧩 Step 5/6: Token chunking & generating semantic embeddings...")
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks: List[DocumentChunk] = []

    if parsed_items:
        doc_chunks = chunker.chunk_document_items(parsed_items)
        all_chunks.extend(doc_chunks)

    if scraped_pages:
        web_chunks = chunker.chunk_scraped_pages(scraped_pages)
        all_chunks.extend(web_chunks)

    st.session_state.all_chunks = all_chunks

    if not all_chunks:
        st.error("No content could be extracted from the uploaded files or URLs.")
        st.stop()

    # Index into Vector Store and Retrieve Top-K
    embedding_engine = EmbeddingEngine()
    vector_store = VectorStore(embedding_engine=embedding_engine)
    vector_store.add_chunks(all_chunks)

    query = f"{research_topic} {user_instructions}"
    retrieved_chunks = vector_store.similarity_search(query=query, top_k=top_k)
    st.session_state.retrieved_chunks = retrieved_chunks
    progress_bar.progress(85)

    # Step 6: Groq Synthesis & PDF Generation
    status_box.info("✍️ Step 6/6: Synthesizing evidence-grounded report & building PDF...")
    synthesizer = GroqSynthesizer(api_key=Config.GROQ_API_KEY, model_name=groq_model)
    report = synthesizer.synthesize(
        retrieved_chunks=retrieved_chunks,
        user_instructions=user_instructions,
        research_topic=research_topic
    )
    st.session_state.report = report

    # Generate PDF
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate_pdf(report)
    st.session_state.pdf_bytes = pdf_bytes

    progress_bar.progress(100)
    status_box.success("🎉 ResearchLens pipeline executed successfully!")


# Display Results
if st.session_state.report:
    report: ResearchReport = st.session_state.report

    tab1, tab2, tab3, tab4 = st.tabs([
        "📑 Final Grounded Report & PDF",
        "🕸️ Web Discovery & LLM Filter",
        "🔍 Retrieved Evidence & Scores",
        "📁 Ingested Documents"
    ])

    with tab1:
        # Download PDF Action
        col_down1, col_down2 = st.columns([3, 1])
        with col_down1:
            st.title(report.title)
        with col_down2:
            if st.session_state.pdf_bytes:
                st.download_button(
                    label="📥 Download Citation-Aware PDF",
                    data=st.session_state.pdf_bytes,
                    file_name="ResearchLens_Summary_Report.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

        st.info(f"**Applied Directives:** {report.instructions_applied}")

        st.subheader("1. Executive Summary")
        st.write(report.executive_summary)

        for idx, sec in enumerate(report.sections, 2):
            st.subheader(f"{idx}. {sec.title}")
            st.write(sec.content)

        if report.comparison_table:
            st.subheader("Comparative Evidence Synthesis")
            table_data = [
                {
                    "Dimension": r.dimension,
                    "Uploaded Document Findings": r.uploaded_findings,
                    "Filtered Web Evidence": r.web_findings,
                    "Synthesized Conclusion": r.synthesis
                }
                for r in report.comparison_table
            ]
            st.table(table_data)

        if report.research_gaps:
            st.subheader("Identified Research Gaps & Future Directions")
            for gap in report.research_gaps:
                st.markdown(f"- {gap}")

        if report.citations:
            st.markdown("---")
            st.subheader("Source Citations & Evidence Base")
            for cit in report.citations:
                badge = "📄 Document" if cit.source_type == "uploaded_document" else "🌐 Web"
                with st.expander(f"[{cit.citation_id}] {badge}: {cit.source_label}"):
                    st.markdown(f"**Reference:** `{cit.url_or_file}`")
                    st.markdown(f"**Location / Section:** {cit.page_or_section}")
                    if cit.snippet:
                        st.caption(f"Excerpt: \"{cit.snippet}\"")

    with tab2:
        st.subheader("Web Discovery & LLM Relevance Filter Decisions")
        st.markdown(
            "Every discovered candidate page is scored by the LLM filter against the research topic and instructions. "
            "Only candidate pages meeting the relevance threshold are extracted into the RAG pipeline."
        )

        if st.session_state.discovered_pages:
            for page in st.session_state.discovered_pages:
                status_color = "🟢" if page.selected else "🔴"
                status_text = "APPROVED" if page.selected else "REJECTED"
                score_str = f"{page.relevance_score}/10" if page.relevance_score is not None else "N/A"

                with st.expander(f"{status_color} [{status_text}] Score: {score_str} — {page.title or page.url}"):
                    st.markdown(f"**URL:** [{page.url}]({page.url})")
                    st.markdown(f"**Crawl Depth:** {page.depth} | **Parent URL:** {page.parent_url or 'Seed URL'}")
                    st.markdown(f"**Filter Decision Reason:** {page.relevance_reason or 'No reason recorded'}")
                    if page.snippet:
                        st.caption(f"Snippet: {page.snippet}")
        else:
            st.info("No web crawling was performed or no candidate URLs were discovered.")

    with tab3:
        st.subheader(f"Top-{len(st.session_state.retrieved_chunks)} Retrieved Chunks (Semantic Vector Retrieval)")
        st.markdown("Inspect similarity scores and source provenance for the chunks retrieved by the vector index.")

        if st.session_state.retrieved_chunks:
            for idx, chunk in enumerate(st.session_state.retrieved_chunks, 1):
                meta = chunk.metadata
                score_display = f"{chunk.score:.4f}" if chunk.score is not None else "N/A"
                source_badge = "📄 Uploaded Doc" if meta.source_type == "uploaded_document" else "🌐 Web Scraped"
                loc = f"Page {meta.page}" if meta.page else (meta.section or meta.url)

                st.markdown(f"##### Chunk #{idx} | Similarity Score: `{score_display}` | {source_badge}")
                st.caption(f"Source: **{meta.filename or meta.title or meta.url}** | Location: {loc} | Tokens: ~{chunk.token_count}")
                st.text_area(f"Chunk Text #{idx}", value=chunk.text, height=120, key=f"chunk_view_{idx}")
                st.markdown("---")
        else:
            st.info("No chunks retrieved yet. Run the pipeline to view semantic retrieval results.")

    with tab4:
        st.subheader("Ingested Documents Overview")
        if st.session_state.ingested_files_info:
            st.table(st.session_state.ingested_files_info)
            st.write(f"**Total chunks generated:** {len(st.session_state.all_chunks)}")
        else:
            st.info("No uploaded files were ingested in this session.")

