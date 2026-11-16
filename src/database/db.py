import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "research_lens.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        topic TEXT NOT NULL,
        directives TEXT,
        preset TEXT DEFAULT 'Standard Brief',
        model TEXT DEFAULT 'openai/gpt-oss-120b',
        crawl_depth INTEGER DEFAULT 1,
        max_pages INTEGER DEFAULT 12,
        same_domain INTEGER DEFAULT 1,
        relevance_threshold REAL DEFAULT 6.0,
        top_k INTEGER DEFAULT 5,
        chunk_size INTEGER DEFAULT 600,
        chunk_overlap INTEGER DEFAULT 100,
        seed_urls TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        parsed_chunks_count INTEGER DEFAULT 0,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS crawled_pages (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT,
        is_relevant INTEGER DEFAULT 1,
        score REAL DEFAULT 0.0,
        reason TEXT,
        content_length INTEGER DEFAULT 0,
        depth INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        executive_summary TEXT,
        detailed_synthesis TEXT,
        comparison_table_json TEXT DEFAULT '[]',
        research_gaps_json TEXT DEFAULT '[]',
        citations_json TEXT DEFAULT '[]',
        pdf_path TEXT,
        model_used TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()


class DatabaseService:
    # --- Project CRUD ---
    @staticmethod
    def create_project(data: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        proj_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        seed_urls_raw = data.get("seed_urls", [])
        seed_urls_json = json.dumps(seed_urls_raw if isinstance(seed_urls_raw, list) else [u.strip() for u in seed_urls_raw.splitlines() if u.strip()])

        conn.execute("""
            INSERT INTO projects (
                id, title, topic, directives, preset, model,
                crawl_depth, max_pages, same_domain, relevance_threshold,
                top_k, chunk_size, chunk_overlap, seed_urls, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proj_id,
            data.get("title", "Untitled Research Project"),
            data.get("topic", "General Research"),
            data.get("directives", ""),
            data.get("preset", "Standard Brief"),
            data.get("model", "openai/gpt-oss-120b"),
            data.get("crawl_depth", 1),
            data.get("max_pages", 12),
            1 if data.get("same_domain", True) else 0,
            float(data.get("relevance_threshold", 6.0)),
            int(data.get("top_k", 5)),
            int(data.get("chunk_size", 600)),
            int(data.get("chunk_overlap", 100)),
            seed_urls_json,
            now,
            now
        ))
        conn.commit()
        conn.close()
        return DatabaseService.get_project(proj_id)  # type: ignore

    @staticmethod
    def get_projects(search: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = """
            SELECT p.*,
                (SELECT COUNT(*) FROM documents WHERE project_id = p.id) AS document_count,
                (SELECT COUNT(*) FROM crawled_pages WHERE project_id = p.id) AS crawled_count,
                (SELECT COUNT(*) FROM reports WHERE project_id = p.id) AS report_count
            FROM projects p
        """
        params: List[Any] = []
        if search:
            query += " WHERE p.title LIKE ? OR p.topic LIKE ?"
            term = f"%{search}%"
            params.extend([term, term])
        query += " ORDER BY p.updated_at DESC"

        rows = conn.execute(query, params).fetchall()
        projects = []
        for row in rows:
            p_dict = dict(row)
            p_dict["seed_urls"] = json.loads(p_dict.get("seed_urls") or "[]")
            p_dict["same_domain"] = bool(p_dict.get("same_domain"))
            projects.append(p_dict)
        conn.close()
        return projects

    @staticmethod
    def get_project(project_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            conn.close()
            return None
        p_dict = dict(row)
        p_dict["seed_urls"] = json.loads(p_dict.get("seed_urls") or "[]")
        p_dict["same_domain"] = bool(p_dict.get("same_domain"))
        
        # Attach counts and latest info
        p_dict["documents"] = DatabaseService.get_documents(project_id)
        p_dict["crawled_pages"] = DatabaseService.get_crawled_pages(project_id)
        p_dict["reports"] = DatabaseService.get_reports(project_id)
        conn.close()
        return p_dict

    @staticmethod
    def update_project(project_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        now = datetime.now(timezone.utc).isoformat()
        seed_urls_raw = data.get("seed_urls")
        seed_urls_json = None
        if seed_urls_raw is not None:
            seed_urls_json = json.dumps(seed_urls_raw if isinstance(seed_urls_raw, list) else [u.strip() for u in seed_urls_raw.splitlines() if u.strip()])

        fields = []
        params = []
        updatable = [
            "title", "topic", "directives", "preset", "model",
            "crawl_depth", "max_pages", "same_domain", "relevance_threshold",
            "top_k", "chunk_size", "chunk_overlap"
        ]
        for field_name in updatable:
            if field_name in data:
                val = data[field_name]
                if field_name == "same_domain":
                    val = 1 if val else 0
                fields.append(f"{field_name} = ?")
                params.append(val)
        
        if seed_urls_json is not None:
            fields.append("seed_urls = ?")
            params.append(seed_urls_json)

        if not fields:
            conn.close()
            return DatabaseService.get_project(project_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(project_id)

        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return DatabaseService.get_project(project_id)

    @staticmethod
    def delete_project(project_id: str) -> bool:
        conn = get_connection()
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    # --- Document CRUD ---
    @staticmethod
    def add_document(project_id: str, filename: str, file_type: str, file_size: int, file_path: str, parsed_chunks_count: int = 0) -> Dict[str, Any]:
        conn = get_connection()
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO documents (id, project_id, filename, file_type, file_size, file_path, parsed_chunks_count, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, project_id, filename, file_type, file_size, file_path, parsed_chunks_count, now))
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.close()
        return dict(row)

    @staticmethod
    def get_documents(project_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM documents WHERE project_id = ? ORDER BY uploaded_at DESC", (project_id,)).fetchall()
        docs = [dict(r) for r in rows]
        conn.close()
        return docs

    @staticmethod
    def delete_document(doc_id: str) -> bool:
        conn = get_connection()
        doc = conn.execute("SELECT project_id, file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            conn.close()
            return False
        
        file_path = Path(doc["file_path"])
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, doc["project_id"]))
        conn.commit()
        conn.close()
        return True

    # --- Crawled Pages CRUD ---
    @staticmethod
    def add_crawled_page(project_id: str, url: str, title: str, is_relevant: bool, score: float, reason: str, content_length: int, depth: int) -> Dict[str, Any]:
        conn = get_connection()
        page_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO crawled_pages (id, project_id, url, title, is_relevant, score, reason, content_length, depth, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (page_id, project_id, url, title, 1 if is_relevant else 0, score, reason, content_length, depth, now))
        conn.commit()
        row = conn.execute("SELECT * FROM crawled_pages WHERE id = ?", (page_id,)).fetchone()
        conn.close()
        res = dict(row)
        res["is_relevant"] = bool(res["is_relevant"])
        return res

    @staticmethod
    def get_crawled_pages(project_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM crawled_pages WHERE project_id = ? ORDER BY score DESC, created_at DESC", (project_id,)).fetchall()
        pages = []
        for r in rows:
            d = dict(r)
            d["is_relevant"] = bool(d["is_relevant"])
            pages.append(d)
        conn.close()
        return pages

    @staticmethod
    def delete_crawled_page(page_id: str) -> bool:
        conn = get_connection()
        cur = conn.execute("DELETE FROM crawled_pages WHERE id = ?", (page_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    @staticmethod
    def clear_crawled_pages(project_id: str) -> bool:
        conn = get_connection()
        conn.execute("DELETE FROM crawled_pages WHERE project_id = ?", (project_id,))
        conn.commit()
        conn.close()
        return True

    # --- Reports CRUD ---
    @staticmethod
    def create_report(project_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        conn = get_connection()
        rep_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn.execute("""
            INSERT INTO reports (
                id, project_id, title, executive_summary, detailed_synthesis,
                comparison_table_json, research_gaps_json, citations_json,
                pdf_path, model_used, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rep_id,
            project_id,
            report_data.get("title", "Research Report"),
            report_data.get("executive_summary", ""),
            report_data.get("detailed_synthesis", ""),
            json.dumps(report_data.get("comparison_table", [])),
            json.dumps(report_data.get("research_gaps", [])),
            json.dumps(report_data.get("citations", [])),
            report_data.get("pdf_path", ""),
            report_data.get("model_used", ""),
            now,
            now
        ))
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
        conn.commit()
        conn.close()
        return DatabaseService.get_report(rep_id)  # type: ignore

    @staticmethod
    def get_reports(project_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM reports WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        reports = []
        for r in rows:
            rep = dict(r)
            rep["comparison_table"] = json.loads(rep.get("comparison_table_json") or "[]")
            rep["research_gaps"] = json.loads(rep.get("research_gaps_json") or "[]")
            rep["citations"] = json.loads(rep.get("citations_json") or "[]")
            reports.append(rep)
        conn.close()
        return reports

    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            conn.close()
            return None
        rep = dict(row)
        rep["comparison_table"] = json.loads(rep.get("comparison_table_json") or "[]")
        rep["research_gaps"] = json.loads(rep.get("research_gaps_json") or "[]")
        rep["citations"] = json.loads(rep.get("citations_json") or "[]")
        conn.close()
        return rep

    @staticmethod
    def update_report(report_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        params = []

        if "title" in update_data:
            fields.append("title = ?")
            params.append(update_data["title"])
        if "executive_summary" in update_data:
            fields.append("executive_summary = ?")
            params.append(update_data["executive_summary"])
        if "detailed_synthesis" in update_data:
            fields.append("detailed_synthesis = ?")
            params.append(update_data["detailed_synthesis"])
        if "comparison_table" in update_data:
            fields.append("comparison_table_json = ?")
            params.append(json.dumps(update_data["comparison_table"]))
        if "research_gaps" in update_data:
            fields.append("research_gaps_json = ?")
            params.append(json.dumps(update_data["research_gaps"]))

        if not fields:
            conn.close()
            return DatabaseService.get_report(report_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(report_id)

        conn.execute(f"UPDATE reports SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return DatabaseService.get_report(report_id)

    @staticmethod
    def delete_report(report_id: str) -> bool:
        conn = get_connection()
        rep = conn.execute("SELECT pdf_path FROM reports WHERE id = ?", (report_id,)).fetchone()
        if rep and rep["pdf_path"]:
            pdf_path = Path(rep["pdf_path"])
            if pdf_path.exists():
                try:
                    pdf_path.unlink()
                except OSError:
                    pass
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
