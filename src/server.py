import os
import shutil
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.config import Config
from src.database.db import DatabaseService, init_db
from src.auth.jwt_handler import hash_password, verify_password, create_access_token, decode_access_token
from src.parsers.document_parser import DocumentParser
from src.scraper.crawler import BoundedCrawler
from src.filter.relevance_filter import RelevanceFilter
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingEngine
from src.rag.vector_store import VectorStore
from src.synthesizer.groq_synthesizer import GroqSynthesizer
from src.exporter.pdf_generator import PDFReportGenerator
from src.models.schemas import ResearchReport, DiscoveredPage, ScrapedPageContent, DocumentChunk

tags_metadata = [
    {
        "name": "Health Check",
        "description": "System health verification, database connectivity status, and supported models.",
    },
    {
        "name": "Authentication",
        "description": "JWT OAuth2 user registration, secure authentication, and profile management.",
    },
    {
        "name": "Projects",
        "description": "Full CRUD operations for managing research projects and study scopes.",
    },
    {
        "name": "Configurations",
        "description": "Project configurations, RAG retrieval parameters, and embedding models.",
    },
    {
        "name": "Documents",
        "description": "Research document upload, format parsing (PDF, DOCX, TXT, CSV), and meaningful chunking.",
    },
    {
        "name": "Web Crawler",
        "description": "Targeted autonomous web scraping, HTML parsing, and LLM relevance filtering.",
    },
    {
        "name": "Reports & Synthesis",
        "description": "RAG evidence synthesis, report generation, and publication-ready PDF exports with visual charts.",
    },
]

app = FastAPI(
    title="ResearchLens API",
    version="2.0.0",
    description="Full-stack AI Research Synthesis Engine with MongoDB, ChromaDB, and BGE Embeddings.",
    openapi_tags=tags_metadata
)

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
Config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()


# --- Security & Current User Dependency ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[Dict[str, Any]]:
    """Validates JWT access token and returns user document from MongoDB."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = payload["sub"]
    user = DatabaseService.get_user_by_id(user_id)
    return user


def require_current_user(user: Optional[Dict[str, Any]] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency that enforces authentication."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# --- Pydantic Request Models ---
class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class ProjectCreateRequest(BaseModel):
    title: str = "Untitled Research Project"
    topic: str = "Retrieval-Augmented Generation (RAG)"
    directives: str = ""
    preset: str = "Standard Brief"
    model: str = "llama-3.3-70b-versatile"
    crawl_depth: int = 1
    max_pages: int = 12
    same_domain: bool = True
    relevance_threshold: float = 6.0
    top_k: int = 5
    chunk_size: int = 600
    chunk_overlap: int = 100
    embedding_model: str = "BAAI/bge-small-en-v1.5"
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
    embedding_model: Optional[str] = None
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


# ==========================================
# --- Authentication Endpoints ---
# ==========================================
@app.post("/api/auth/register", status_code=201, tags=["Authentication"], summary="Register a new user account")
def register(req: UserRegisterRequest):
    # Check if username or email already exists
    if DatabaseService.get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="Username is already taken.")
    if DatabaseService.get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email is already registered.")

    hashed = hash_password(req.password)
    user = DatabaseService.create_user(
        username=req.username,
        email=req.email,
        hashed_password=hashed
    )
    token = create_access_token({"sub": user["id"], "username": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "user")
        }
    }


@app.post("/api/auth/login", tags=["Authentication"], summary="User login and JWT access token acquisition")
def login(req: UserLoginRequest):
    user = DatabaseService.get_user_by_username(req.username)
    if not user:
        # Also allow login with email
        user = DatabaseService.get_user_by_email(req.username)

    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_access_token({"sub": user["id"], "username": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "user")
        }
    }


@app.get("/api/auth/me", tags=["Authentication"], summary="Get authenticated user profile")
def get_me(user: Dict[str, Any] = Depends(require_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user.get("role", "user")
    }


# ==========================================
# --- Health Check & System Endpoints ---
# ==========================================
@app.get("/api/health", tags=["Health Check"], summary="Check system health and database status")
def get_health():
    return {
        "status": "healthy",
        "database": "mongodb",
        "mongodb_uri": Config.MONGODB_URI,
        "vector_store": "chromadb",
        "embedding_model": Config.EMBEDDING_MODEL,
        "has_groq_key": bool(Config.GROQ_API_KEY),
        "default_model": Config.GROQ_MODEL,
        "default_filter_model": Config.GROQ_FILTER_MODEL
    }


@app.get("/api/models", tags=["Health Check"], summary="List available Groq LLM reasoning models")
def get_models():
    return {
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "mixtral-8x7b-32768"
        ],
        "default": Config.GROQ_MODEL
    }


@app.get("/api/embedding-models", tags=["Health Check"], summary="List supported sentence embedding models")
def get_embedding_models():
    return {
        "models": [
            "BAAI/bge-small-en-v1.5",
            "all-MiniLM-L6-v2",
            "all-mpnet-base-v2",
            "nomic-ai/nomic-embed-text-v1.5"
        ],
        "default": Config.EMBEDDING_MODEL
    }


@app.get("/api/presets", tags=["Health Check"], summary="List research instruction presets")
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


# ==========================================
# --- Project Endpoints (CRUD) ---
# ==========================================
@app.get("/api/projects", tags=["Projects"], summary="List research projects")
def list_projects(
    search: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    user_id = current_user["id"] if current_user else None
    return DatabaseService.get_projects(search=search, user_id=user_id)


@app.post("/api/projects", status_code=201, tags=["Projects"], summary="Create new research project")
def create_project(
    req: ProjectCreateRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    user_id = current_user["id"] if current_user else None
    return DatabaseService.create_project(req.model_dump(), user_id=user_id)


@app.get("/api/projects/{project_id}", tags=["Projects"], summary="Get research project by ID")
def get_project(
    project_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    user_id = current_user["id"] if current_user else None
    proj = DatabaseService.get_project(project_id, user_id=user_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.put("/api/projects/{project_id}", tags=["Projects"], summary="Update research project parameters")
def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    user_id = current_user["id"] if current_user else None
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    proj = DatabaseService.update_project(project_id, update_data, user_id=user_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.delete("/api/projects/{project_id}", tags=["Projects"], summary="Delete research project and cascade related data")
def delete_project(
    project_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    user_id = current_user["id"] if current_user else None
    success = DatabaseService.delete_project(project_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted", "id": project_id}


# ==========================================
# --- Configuration Endpoints ---
# ==========================================
@app.get("/api/projects/{project_id}/configuration", tags=["Configurations"], summary="Get project configuration and RAG parameters")
def get_project_configuration(
    project_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    config = DatabaseService.get_configuration(project_id)
    return config or {}


@app.put("/api/projects/{project_id}/configuration", tags=["Configurations"], summary="Update project configuration and RAG parameters")
def update_project_configuration(
    project_id: str,
    config: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    user_id = current_user["id"] if current_user else None
    return DatabaseService.save_configuration(project_id, config, user_id=user_id)


# ==========================================
# --- Document Upload & Chunks (CRUD) ---
# ==========================================
@app.get("/api/projects/{project_id}/documents", tags=["Documents"], summary="List uploaded research documents")
def list_documents(project_id: str):
    return DatabaseService.get_documents(project_id)


@app.post("/api/projects/{project_id}/documents", tags=["Documents"], summary="Upload research files (PDF, DOCX, TXT, CSV, XLSX, MD)")
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    user_id = current_user["id"] if current_user else None
    uploaded = []
    chunker = DocumentChunker(chunk_size=proj["chunk_size"], chunk_overlap=proj["chunk_overlap"])

    for file in files:
        filename = file.filename or "unknown_file"
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in ["pdf", "docx", "txt", "csv", "xlsx", "doc", "xls"]:
            raise HTTPException(status_code=400, detail=f"Unsupported format: .{ext}")

        dest_filename = f"{project_id}_{filename}"
        dest_path = UPLOAD_DIR / dest_filename

        content = await file.read()
        dest_path.write_bytes(content)

        # Parse and count chunks using meaningful sentence chunking
        try:
            items = DocumentParser.parse_file(str(dest_path), original_filename=filename)
            chunks = chunker.chunk_document_items(items)
            chunk_count = len(chunks)
        except Exception as e:
            chunk_count = 0

        doc_record = DatabaseService.add_document(
            project_id=project_id,
            filename=filename,
            file_type=ext,
            file_size=len(content),
            file_path=str(dest_path),
            parsed_chunks_count=chunk_count,
            user_id=user_id
        )
        uploaded.append(doc_record)

    return uploaded


@app.get("/api/documents/{doc_id}/chunks", tags=["Documents"], summary="Inspect parsed chunks and metadata for document")
def inspect_chunks(doc_id: str):
    # Find document in MongoDB
    docs = DatabaseService.get_documents_collection().find_one({"id": doc_id})
    if not docs:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = docs["file_path"]
    filename = docs["filename"]

    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File on disk no longer exists")

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


@app.delete("/api/documents/{doc_id}", tags=["Documents"], summary="Delete uploaded research document")
def delete_document(doc_id: str):
    success = DatabaseService.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted", "id": doc_id}


# ==========================================
# --- Crawl & Web Evidence Endpoints ---
# ==========================================
@app.get("/api/projects/{project_id}/crawled-pages", tags=["Web Crawler"], summary="List crawled and relevance-filtered web pages")
def list_crawled_pages(project_id: str):
    return DatabaseService.get_crawled_pages(project_id)


@app.post("/api/projects/{project_id}/crawl", tags=["Web Crawler"], summary="Trigger autonomous web crawl and LLM relevance filtering")
def trigger_crawl(
    project_id: str,
    req: Optional[CrawlRequest] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    user_id = current_user["id"] if current_user else None
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
            depth=cand.depth,
            user_id=user_id
        )
        created_pages.append(c_page)

    return {
        "discovered_count": len(discovered_candidates),
        "relevant_count": len(selected_pages),
        "pages": created_pages
    }


@app.delete("/api/crawled-pages/{page_id}", tags=["Web Crawler"], summary="Delete an individual crawled web page")
def delete_crawled_page(page_id: str):
    success = DatabaseService.delete_crawled_page(page_id)
    if not success:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"message": "Page deleted", "id": page_id}


@app.delete("/api/projects/{project_id}/crawled-pages", tags=["Web Crawler"], summary="Clear all crawled web pages for project")
def clear_all_crawled_pages(project_id: str):
    DatabaseService.clear_crawled_pages(project_id)
    return {"message": "All crawled pages cleared"}


# ==========================================
# --- Synthesis & Reports (Final Output PDF) ---
# ==========================================
@app.get("/api/projects/{project_id}/reports", tags=["Reports & Synthesis"], summary="List synthesized research reports for project")
def list_reports(project_id: str):
    return DatabaseService.get_reports(project_id)


@app.get("/api/reports/{report_id}", tags=["Reports & Synthesis"], summary="Get synthesized research report details")
def get_report(report_id: str):
    rep = DatabaseService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep


@app.put("/api/reports/{report_id}", tags=["Reports & Synthesis"], summary="Update report content, synthesis sections, or research gaps")
def update_report(report_id: str, req: ReportUpdateRequest):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    rep = DatabaseService.update_report(report_id, update_data)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep


@app.delete("/api/reports/{report_id}", tags=["Reports & Synthesis"], summary="Delete synthesized report")
def delete_report(report_id: str):
    success = DatabaseService.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted", "id": report_id}


@app.post("/api/projects/{project_id}/generate-report", tags=["Reports & Synthesis"], summary="Execute RAG synthesis and generate publication-ready PDF report with charts")
def generate_report(
    project_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    proj = DatabaseService.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    user_id = current_user["id"] if current_user else None
    docs = DatabaseService.get_documents(project_id)
    crawled_pages = DatabaseService.get_crawled_pages(project_id)

    if not docs and not crawled_pages:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate report: Please upload at least one document or run a crawl on seed URLs first."
        )

    try:
        # 1. Parse all documents with data cleaning pipeline
        parsed_items = []
        for d in docs:
            if Path(d["file_path"]).exists():
                try:
                    items = DocumentParser.parse_file(d["file_path"], original_filename=d["filename"])
                    parsed_items.extend(items)
                except Exception as e:
                    print(f"Warning parsing document {d['filename']}: {e}")

        # 2. Chunk documents with NLTK sentence-aware meaningful chunker
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

        # 4. RAG Indexing & Top-K Retrieval via ChromaDB
        embedding_engine = EmbeddingEngine(model_name=proj.get("embedding_model", Config.EMBEDDING_MODEL))
        vector_store = VectorStore(embedding_engine=embedding_engine, project_id=project_id)
        vector_store.clear()
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

        # 6. Generate Publication-Ready PDF with Visual Charts
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_pdf(synth_report)

        # Save PDF to disk
        pdf_filename = f"report_{proj['id'][:8]}_{len(DatabaseService.get_reports(project_id)) + 1}.pdf"
        pdf_path = Config.EXPORTS_DIR / pdf_filename
        pdf_path.write_bytes(pdf_bytes)

        detailed_synthesis_text = "\n\n".join(
            f"### {sec.title}\n\n{sec.content}" for sec in synth_report.sections
        ) if synth_report.sections else ""

        # 7. Save Report in MongoDB reports collection
        report_dict = DatabaseService.create_report(
            project_id=project_id,
            report_data={
                "title": synth_report.title,
                "executive_summary": synth_report.executive_summary,
                "detailed_synthesis": detailed_synthesis_text,
                "comparison_table": [r.model_dump() for r in (synth_report.comparison_table or [])],
                "research_gaps": synth_report.research_gaps or [],
                "citations": [c.model_dump() for c in (synth_report.citations or [])],
                "pdf_path": str(pdf_path),
                "model_used": proj["model"]
            },
            user_id=user_id
        )

        return report_dict
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during report generation: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation error: {str(e)}") from e


@app.get("/api/reports/{report_id}/pdf", tags=["Reports & Synthesis"], summary="Download publication-ready PDF document with charts")
def download_pdf(report_id: str):
    rep = DatabaseService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")

    filename = f"{rep['title'].replace(' ', '_')[:40]}.pdf"
    pdf_path_str = rep.get("pdf_path")

    # 1. Check local file system
    if pdf_path_str and Path(pdf_path_str).exists():
        return FileResponse(
            path=str(pdf_path_str),
            media_type="application/pdf",
            filename=filename
        )

    # 2. Check MongoDB stored base64 representation
    if rep.get("pdf_base64"):
        pdf_bytes = base64.b64decode(rep["pdf_base64"])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    raise HTTPException(status_code=404, detail="PDF document could not be located")


# --- Frontend Static Files (Single-page App Serving) ---
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
