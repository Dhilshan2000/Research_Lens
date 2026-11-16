import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.config import Config
from src.database.db import DatabaseService, init_db
from src.parsers.document_parser import DocumentParser
from src.scraper.crawler import BoundedCrawler
from src.filter.relevance_filter import RelevanceFilter
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingEngine
from src.rag.vector_store import VectorStore
from src.synthesizer.groq_synthesizer import GroqSynthesizer
from src.exporter.pdf_generator import PDFReportGenerator
from src.models.schemas import ResearchReport, DiscoveredPage, ScrapedPageContent, DocumentChunk

app = FastAPI(title="ResearchLens API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Config.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
Config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()


# --- Pydantic Request Models ---
class ProjectCreateRequest(BaseModel):
    title: str = "Untitled Research Project"
    topic: str = "Retrieval-Augmented Generation (RAG)"
    directives: str = ""
    preset: str = "Standard Brief"
    model: str = "openai/gpt-oss-120b"
    crawl_depth: int = 1
    max_pages: int = 12
    same_domain: bool = True
    relevance_threshold: float = 6.0
    top_k: int = 5
    chunk_size: int = 600
    chunk_overlap: int = 100
    seed_urls: List[str] = Field(default_factory=list)


class ProjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    directives: Optional[str] = None
    preset: Optional[str] = None
    model: Optional[str] = None
    crawl_depth: Optional[int] = None
    max_pages: Optional[int] = None
    same_domain: Optional[bool] = None
    relevance_threshold: Optional[float] = None
    top_k: Optional[int] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    seed_urls: Optional[List[str]] = None


class CrawlRequest(BaseModel):
    seed_urls: Optional[List[str]] = None
    crawl_depth: Optional[int] = None
    max_pages: Optional[int] = None
    same_domain: Optional[bool] = None
    relevance_threshold: Optional[float] = None


class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    detailed_synthesis: Optional[str] = None
    comparison_table: Optional[List[Dict[str, Any]]] = None
    research_gaps: Optional[List[str]] = None


# --- System & Config Endpoints ---
@app.get("/api/health")
def get_health():
    return {
        "status": "healthy",
        "has_groq_key": bool(Config.GROQ_API_KEY),
        "default_model": Config.GROQ_MODEL,
        "default_filter_model": Config.GROQ_FILTER_MODEL
    }


@app.get("/api/models")
def get_models():
    return {
        "models": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768"
        ],
        "default": Config.GROQ_MODEL
    }


@app.get("/api/presets")
def get_presets():
    return [
        {
            "id": "Standard Brief",
            "name": "Standard Brief (Academic tone, research gaps, comparison table, under 4 pages)",
            "text": (
                "Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages. "
                "Critically analyze the methodology, empirical results, and contrast the uploaded findings with recent external web evidence."
            )
        },
        {
            "id": "Literature Review & Methodological Analysis",
            "name": "Literature Review & Methodological Analysis",
            "text": (
                "Provide a rigorous comparative literature review. Focus on algorithm design, experimental datasets, benchmark evaluations, "
                "and contrast theoretical claims from the uploaded papers against real-world web implementations. Include a comparison table."
            )
        },
        {
            "id": "Executive Briefing & Strategic Gaps",
            "name": "Executive Briefing & Strategic Gaps",
            "text": (
                "Deliver an executive briefing summarizing business implications, architectural trade-offs, and critical gaps in adoption. "
                "Maintain a formal professional tone, highlight key bottlenecks, and construct a synthesis comparison matrix."
            )
        },
        {
            "id": "Custom Directives",
            "name": "Custom Directives",
            "text": ""
        }
    ]


# --- Project Endpoints (CRUD) ---
@app.get("/api/projects")
def list_projects(search: Optional[str] = Query(None)):
    return DatabaseService.get_projects(search=search)


@app.post("/api/projects", status_code=201)
def create_project(req: ProjectCreateRequest):
    return DatabaseService.create_project(req.model_dump())


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, req: ProjectUpdateRequest):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    proj = DatabaseService.update_project(project_id, update_data)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    success = DatabaseService.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    proj_folder = UPLOAD_DIR / project_id
    if proj_folder.exists():
        shutil.rmtree(proj_folder, ignore_errors=True)
    return {"message": "Project deleted successfully", "id": project_id}


# --- Document Endpoints (CRUD) ---
@app.get("/api/projects/{project_id}/documents")
def list_project_documents(project_id: str):
    return DatabaseService.get_documents(project_id)


@app.post("/api/projects/{project_id}/documents")
async def upload_documents(project_id: str, files: List[UploadFile] = File(...)):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = UPLOAD_DIR / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    created_docs = []
    chunker = DocumentChunker(chunk_size=proj["chunk_size"], chunk_overlap=proj["chunk_overlap"])

    for file in files:
        file_path = proj_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)

        chunks_count = 0
        try:
            items = DocumentParser.parse_file(str(file_path), original_filename=file.filename)
            chunks = chunker.chunk_document_items(items)
            chunks_count = len(chunks)
        except Exception:
            chunks_count = 0

        ext = file_path.suffix.lstrip(".").lower()
        doc = DatabaseService.add_document(
            project_id=project_id,
            filename=file.filename,
            file_type=ext,
            file_size=len(content),
            file_path=str(file_path),
            parsed_chunks_count=chunks_count
        )
        created_docs.append(doc)

    return created_docs


@app.get("/api/documents/{doc_id}/chunks")
def inspect_document_chunks(doc_id: str):
    from src.database.db import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = row["file_path"]
    filename = row["filename"]
    try:
        items = DocumentParser.parse_file(file_path, original_filename=filename)
        chunker = DocumentChunker(chunk_size=600, chunk_overlap=100)
        chunks = chunker.chunk_document_items(items)
        return {
            "document_id": doc_id,
            "filename": filename,
            "total_chunks": len(chunks),
            "chunks": [c.model_dump() for c in chunks]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to inspect chunks: {str(e)}")


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    success = DatabaseService.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted", "id": doc_id}


# --- Crawl & Web Evidence Endpoints (CRUD) ---
@app.get("/api/projects/{project_id}/crawled-pages")
def list_crawled_pages(project_id: str):
    return DatabaseService.get_crawled_pages(project_id)


@app.post("/api/projects/{project_id}/crawl")
def trigger_crawl(project_id: str, req: Optional[CrawlRequest] = None):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    seed_urls = (req.seed_urls if req and req.seed_urls else proj.get("seed_urls", []))
    if not seed_urls:
        raise HTTPException(status_code=400, detail="No seed URLs configured for crawl.")

    crawl_depth = req.crawl_depth if req and req.crawl_depth is not None else proj.get("crawl_depth", 1)
    max_pages = req.max_pages if req and req.max_pages is not None else proj.get("max_pages", 12)
    same_domain = req.same_domain if req and req.same_domain is not None else proj.get("same_domain", True)
    relevance_threshold = req.relevance_threshold if req and req.relevance_threshold is not None else proj.get("relevance_threshold", 6.0)

    # Clear previous crawl records
    DatabaseService.clear_crawled_pages(project_id)

    crawler = BoundedCrawler(
        max_depth=crawl_depth,
        max_pages=max_pages,
        same_domain_only=same_domain
    )
    discovered_candidates = crawler.discover_candidates(seed_urls)

    rel_filter = RelevanceFilter(
        api_key=Config.GROQ_API_KEY,
        model_name=Config.GROQ_FILTER_MODEL,
        threshold=relevance_threshold
    )
    selected_pages = rel_filter.evaluate_candidates(
        discovered_candidates,
        user_instructions=proj["directives"],
        research_topic=proj["topic"]
    )

    selected_urls = {p.url for p in selected_pages}
    decisions = getattr(rel_filter, "last_decisions", {})

    created_pages = []
    for cand in discovered_candidates:
        dec = decisions.get(cand.url)
        is_relevant = cand.url in selected_urls
        score = dec.score if dec else (7.0 if is_relevant else 3.0)
        reason = dec.reason if dec else ("Approved as relevant" if is_relevant else "Below threshold or non-informative")
        
        c_page = DatabaseService.add_crawled_page(
            project_id=project_id,
            url=cand.url,
            title=cand.title or cand.url,
            is_relevant=is_relevant,
            score=score,
            reason=reason,
            content_length=len(cand.snippet or ""),
            depth=cand.depth
        )
        created_pages.append(c_page)

    return {
        "discovered_count": len(discovered_candidates),
        "relevant_count": len(selected_pages),
        "pages": created_pages
    }


@app.delete("/api/crawled-pages/{page_id}")
def delete_crawled_page(page_id: str):
    success = DatabaseService.delete_crawled_page(page_id)
    if not success:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"message": "Page deleted", "id": page_id}


@app.delete("/api/projects/{project_id}/crawled-pages")
def clear_all_crawled_pages(project_id: str):
    DatabaseService.clear_crawled_pages(project_id)
    return {"message": "All crawled pages cleared"}


# --- Synthesis & Reports Endpoints (CRUD) ---
@app.get("/api/projects/{project_id}/reports")
def list_reports(project_id: str):
    return DatabaseService.get_reports(project_id)


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    rep = DatabaseService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep


@app.put("/api/reports/{report_id}")
def update_report(report_id: str, req: ReportUpdateRequest):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    rep = DatabaseService.update_report(report_id, update_data)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: str):
    success = DatabaseService.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted", "id": report_id}


@app.post("/api/projects/{project_id}/generate-report")
def generate_report(project_id: str):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    docs = DatabaseService.get_documents(project_id)
    crawled_pages = DatabaseService.get_crawled_pages(project_id)

    if not docs and not crawled_pages:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate report: Please upload at least one document or run a crawl on seed URLs first."
        )

    # 1. Parse all documents
    parsed_items = []
    for d in docs:
        if Path(d["file_path"]).exists():
            try:
                items = DocumentParser.parse_file(d["file_path"], original_filename=d["filename"])
                parsed_items.extend(items)
            except Exception as e:
                print(f"Warning parsing document {d['filename']}: {e}")

    # 2. Chunk documents
    chunker = DocumentChunker(chunk_size=proj["chunk_size"], chunk_overlap=proj["chunk_overlap"])
    all_chunks: List[DocumentChunk] = []
    if parsed_items:
        doc_chunks = chunker.chunk_document_items(parsed_items)
        all_chunks.extend(doc_chunks)

    # 3. Extract and chunk relevant crawled pages
    relevant_crawled = [cp for cp in crawled_pages if cp["is_relevant"]]
    if relevant_crawled:
        crawler = BoundedCrawler(same_domain_only=proj.get("same_domain", True))
        selected_pages = [
            DiscoveredPage(
                url=cp["url"],
                title=cp["title"],
                snippet="",
                depth=cp["depth"]
            )
            for cp in relevant_crawled
        ]
        scraped_pages: List[ScrapedPageContent] = crawler.extract_selected(selected_pages)
        if scraped_pages:
            web_chunks = chunker.chunk_scraped_pages(scraped_pages)
            all_chunks.extend(web_chunks)

    if not all_chunks:
        raise HTTPException(status_code=400, detail="No text chunks could be extracted from sources.")

    # 4. RAG Indexing & Top-K Retrieval
    embedding_engine = EmbeddingEngine()
    vector_store = VectorStore(embedding_engine=embedding_engine)
    vector_store.add_chunks(all_chunks)

    query = f"{proj['topic']} {proj['directives']}"
    retrieved_chunks = vector_store.similarity_search(query=query, top_k=proj["top_k"])

    # 5. Groq Synthesizer
    synthesizer = GroqSynthesizer(api_key=Config.GROQ_API_KEY, model_name=proj["model"])
    synth_report: ResearchReport = synthesizer.synthesize(
        retrieved_chunks=retrieved_chunks,
        user_instructions=proj["directives"],
        research_topic=proj["topic"]
    )

    # 6. Generate Publication-Ready PDF
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate_pdf(synth_report)
    
    # Save PDF to disk
    pdf_filename = f"report_{proj['id'][:8]}_{len(DatabaseService.get_reports(project_id)) + 1}.pdf"
    pdf_path = Config.EXPORTS_DIR / pdf_filename
    pdf_path.write_bytes(pdf_bytes)

    # 7. Save Report in Database
    report_dict = DatabaseService.create_report(
        project_id=project_id,
        report_data={
            "title": synth_report.title,
            "executive_summary": synth_report.executive_summary,
            "detailed_synthesis": synth_report.detailed_synthesis,
            "comparison_table": [r.model_dump() for r in synth_report.comparison_table],
            "research_gaps": synth_report.research_gaps,
            "citations": [c.model_dump() for c in synth_report.citations],
            "pdf_path": str(pdf_path),
            "model_used": proj["model"]
        }
    )

    return report_dict


@app.get("/api/reports/{report_id}/pdf")
def download_pdf(report_id: str):
    rep = DatabaseService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    
    pdf_path = Path(rep["pdf_path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    filename = f"{rep['title'].replace(' ', '_')[:40]}.pdf"
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename
    )


# --- Frontend Static Files (Single-page App Serving) ---
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

