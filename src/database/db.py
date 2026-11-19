import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from bson import ObjectId

from .mongo import (
    init_mongo,
    get_users_collection,
    get_documents_collection,
    get_reports_collection,
    get_configurations_collection,
    get_projects_collection,
    get_crawled_pages_collection,
)


def init_db() -> None:
    """Initializes MongoDB database and collections."""
    init_mongo()


def _serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Converts MongoDB BSON document to clean JSON-serializable dictionary."""
    if not doc:
        return None
    res = dict(doc)
    if "_id" in res:
        # Preserve string id for compatibility with existing APIs
        res["id"] = res.get("id") or str(res["_id"])
        del res["_id"]
    return res


class DatabaseService:
    # ==========================================
    # --- User Management (Authentication) ---
    # ==========================================
    @staticmethod
    def create_user(username: str, email: str, hashed_password: str, role: str = "user") -> Dict[str, Any]:
        coll = get_users_collection()
        now = datetime.now(timezone.utc).isoformat()
        user_doc = {
            "id": str(uuid.uuid4()),
            "username": username.strip(),
            "email": email.strip().lower(),
            "hashed_password": hashed_password,
            "role": role,
            "created_at": now,
            "updated_at": now
        }
        res = coll.insert_one(user_doc)
        user_doc["id"] = user_doc.get("id") or str(res.inserted_id)
        return _serialize_doc(user_doc)  # type: ignore

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        coll = get_users_collection()
        doc = coll.find_one({"$or": [{"id": user_id}, {"_id": ObjectId(user_id) if ObjectId.is_valid(user_id) else None}]})
        return _serialize_doc(doc)

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        coll = get_users_collection()
        doc = coll.find_one({"username": username.strip()})
        return _serialize_doc(doc)

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        coll = get_users_collection()
        doc = coll.find_one({"email": email.strip().lower()})
        return _serialize_doc(doc)

    # ==========================================
    # --- Configurations Management ---
    # ==========================================
    @staticmethod
    def save_configuration(project_id: str, config_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        coll = get_configurations_collection()
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "project_id": project_id,
            "user_id": user_id,
            "model": config_data.get("model", "llama-3.3-70b-versatile"),
            "directives": config_data.get("directives", ""),
            "preset": config_data.get("preset", "Standard Brief"),
            "crawl_depth": int(config_data.get("crawl_depth", 1)),
            "max_pages": int(config_data.get("max_pages", 12)),
            "same_domain": bool(config_data.get("same_domain", True)),
            "relevance_threshold": float(config_data.get("relevance_threshold", 6.0)),
            "top_k": int(config_data.get("top_k", 5)),
            "chunk_size": int(config_data.get("chunk_size", 600)),
            "chunk_overlap": int(config_data.get("chunk_overlap", 100)),
            "embedding_model": config_data.get("embedding_model", "BAAI/bge-small-en-v1.5"),
            "updated_at": now
        }
        coll.update_one({"project_id": project_id}, {"$set": payload, "$setOnInsert": {"created_at": now}}, upsert=True)
        return DatabaseService.get_configuration(project_id)  # type: ignore

    @staticmethod
    def get_configuration(project_id: str) -> Optional[Dict[str, Any]]:
        coll = get_configurations_collection()
        doc = coll.find_one({"project_id": project_id})
        return _serialize_doc(doc)

    # ==========================================
    # --- Project CRUD ---
    # ==========================================
    @staticmethod
    def create_project(data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        coll = get_projects_collection()
        proj_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        seed_urls_raw = data.get("seed_urls", [])
        if isinstance(seed_urls_raw, list):
            seed_urls = seed_urls_raw
        else:
            seed_urls = [u.strip() for u in str(seed_urls_raw).splitlines() if u.strip()]

        project_doc = {
            "id": proj_id,
            "user_id": user_id,
            "title": data.get("title", "Untitled Research Project"),
            "topic": data.get("topic", "General Research"),
            "directives": data.get("directives", ""),
            "preset": data.get("preset", "Standard Brief"),
            "model": data.get("model", "llama-3.3-70b-versatile"),
            "crawl_depth": int(data.get("crawl_depth", 1)),
            "max_pages": int(data.get("max_pages", 12)),
            "same_domain": bool(data.get("same_domain", True)),
            "relevance_threshold": float(data.get("relevance_threshold", 6.0)),
            "top_k": int(data.get("top_k", 5)),
            "chunk_size": int(data.get("chunk_size", 600)),
            "chunk_overlap": int(data.get("chunk_overlap", 100)),
            "embedding_model": data.get("embedding_model", "BAAI/bge-small-en-v1.5"),
            "seed_urls": seed_urls,
            "created_at": now,
            "updated_at": now
        }
        coll.insert_one(project_doc)

        # Store initial project configuration in 'configurations' collection
        DatabaseService.save_configuration(proj_id, project_doc, user_id=user_id)

        return DatabaseService.get_project(proj_id)  # type: ignore

    @staticmethod
    def get_projects(search: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        coll = get_projects_collection()
        filter_query: Dict[str, Any] = {}
        if user_id:
            filter_query["user_id"] = user_id

        if search:
            regex_term = {"$regex": search, "$options": "i"}
            filter_query["$or"] = [{"title": regex_term}, {"topic": regex_term}]

        cursor = coll.find(filter_query).sort("updated_at", -1)
        projects = []
        for p in cursor:
            p_dict = _serialize_doc(p)
            proj_id = p_dict["id"]
            p_dict["document_count"] = get_documents_collection().count_documents({"project_id": proj_id})
            p_dict["crawled_count"] = get_crawled_pages_collection().count_documents({"project_id": proj_id})
            p_dict["report_count"] = get_reports_collection().count_documents({"project_id": proj_id})
            projects.append(p_dict)
        return projects

    @staticmethod
    def get_project(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        coll = get_projects_collection()
        query: Dict[str, Any] = {"id": project_id}
        if user_id:
            query["user_id"] = user_id
        doc = coll.find_one(query)
        if not doc:
            return None

        p_dict = _serialize_doc(doc)
        p_dict["documents"] = DatabaseService.get_documents(project_id)
        p_dict["crawled_pages"] = DatabaseService.get_crawled_pages(project_id)
        p_dict["reports"] = DatabaseService.get_reports(project_id)
        p_dict["configuration"] = DatabaseService.get_configuration(project_id)
        return p_dict

    @staticmethod
    def update_project(project_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        coll = get_projects_collection()
        now = datetime.now(timezone.utc).isoformat()
        query: Dict[str, Any] = {"id": project_id}
        if user_id:
            query["user_id"] = user_id

        update_fields: Dict[str, Any] = {}
        updatable = [
            "title", "topic", "directives", "preset", "model",
            "crawl_depth", "max_pages", "same_domain", "relevance_threshold",
            "top_k", "chunk_size", "chunk_overlap", "embedding_model"
        ]
        for field in updatable:
            if field in data and data[field] is not None:
                update_fields[field] = data[field]

        if "seed_urls" in data and data["seed_urls"] is not None:
            raw = data["seed_urls"]
            seed_urls = raw if isinstance(raw, list) else [u.strip() for u in str(raw).splitlines() if u.strip()]
            update_fields["seed_urls"] = seed_urls

        if not update_fields:
            return DatabaseService.get_project(project_id, user_id)

        update_fields["updated_at"] = now
        coll.update_one(query, {"$set": update_fields})

        # Update configurations collection as well
        DatabaseService.save_configuration(project_id, update_fields, user_id=user_id)

        return DatabaseService.get_project(project_id, user_id)

    @staticmethod
    def delete_project(project_id: str, user_id: Optional[str] = None) -> bool:
        coll = get_projects_collection()
        query: Dict[str, Any] = {"id": project_id}
        if user_id:
            query["user_id"] = user_id

        res = coll.delete_one(query)
        if res.deleted_count > 0:
            # Cascade delete in related collections
            get_documents_collection().delete_many({"project_id": project_id})
            get_crawled_pages_collection().delete_many({"project_id": project_id})
            get_reports_collection().delete_many({"project_id": project_id})
            get_configurations_collection().delete_many({"project_id": project_id})
            return True
        return False

    # ==========================================
    # --- Document CRUD ---
    # ==========================================
    @staticmethod
    def add_document(
        project_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        file_path: str,
        parsed_chunks_count: int = 0,
        user_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        coll = get_documents_collection()
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc_record = {
            "id": doc_id,
            "project_id": project_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "file_path": str(file_path),
            "parsed_chunks_count": parsed_chunks_count,
            "extra_metadata": extra_metadata or {},
            "uploaded_at": now
        }
        coll.insert_one(doc_record)
        get_projects_collection().update_one({"id": project_id}, {"$set": {"updated_at": now}})
        return _serialize_doc(doc_record)  # type: ignore

    @staticmethod
    def get_documents(project_id: str) -> List[Dict[str, Any]]:
        coll = get_documents_collection()
        cursor = coll.find({"project_id": project_id}).sort("uploaded_at", -1)
        return [_serialize_doc(d) for d in cursor]

    @staticmethod
    def delete_document(doc_id: str) -> bool:
        coll = get_documents_collection()
        doc = coll.find_one({"id": doc_id})
        if not doc:
            return False

        file_path = Path(doc["file_path"])
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass

        coll.delete_one({"id": doc_id})
        now = datetime.now(timezone.utc).isoformat()
        get_projects_collection().update_one({"id": doc["project_id"]}, {"$set": {"updated_at": now}})
        return True

    # ==========================================
    # --- Crawled Pages CRUD ---
    # ==========================================
    @staticmethod
    def add_crawled_page(
        project_id: str,
        url: str,
        title: str,
        is_relevant: bool,
        score: float,
        reason: str,
        content_length: int,
        depth: int,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        coll = get_crawled_pages_collection()
        page_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        page_doc = {
            "id": page_id,
            "project_id": project_id,
            "user_id": user_id,
            "url": url,
            "title": title,
            "is_relevant": is_relevant,
            "score": score,
            "reason": reason,
            "content_length": content_length,
            "depth": depth,
            "created_at": now
        }
        coll.insert_one(page_doc)
        return _serialize_doc(page_doc)  # type: ignore

    @staticmethod
    def get_crawled_pages(project_id: str) -> List[Dict[str, Any]]:
        coll = get_crawled_pages_collection()
        cursor = coll.find({"project_id": project_id}).sort([("score", -1), ("created_at", -1)])
        return [_serialize_doc(p) for p in cursor]

    @staticmethod
    def delete_crawled_page(page_id: str) -> bool:
        coll = get_crawled_pages_collection()
        res = coll.delete_one({"id": page_id})
        return res.deleted_count > 0

    @staticmethod
    def clear_crawled_pages(project_id: str) -> bool:
        coll = get_crawled_pages_collection()
        coll.delete_many({"project_id": project_id})
        return True

    # ==========================================
    # --- Reports CRUD (Final Output PDF Document) ---
    # ==========================================
    @staticmethod
    def create_report(project_id: str, report_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        coll = get_reports_collection()
        rep_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        pdf_path = report_data.get("pdf_path", "")
        pdf_base64 = ""
        # Store base64 representation in MongoDB for reliable portability
        if pdf_path and Path(pdf_path).exists():
            try:
                pdf_bytes = Path(pdf_path).read_bytes()
                pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
            except Exception:
                pass

        report_doc = {
            "id": rep_id,
            "project_id": project_id,
            "user_id": user_id,
            "title": report_data.get("title", "Research Report"),
            "executive_summary": report_data.get("executive_summary", ""),
            "detailed_synthesis": report_data.get("detailed_synthesis", ""),
            "comparison_table": report_data.get("comparison_table", []),
            "research_gaps": report_data.get("research_gaps", []),
            "citations": report_data.get("citations", []),
            "pdf_path": str(pdf_path),
            "pdf_base64": pdf_base64,
            "model_used": report_data.get("model_used", ""),
            "created_at": now,
            "updated_at": now
        }
        coll.insert_one(report_doc)
        get_projects_collection().update_one({"id": project_id}, {"$set": {"updated_at": now}})
        return _serialize_doc(report_doc)  # type: ignore

    @staticmethod
    def get_reports(project_id: str) -> List[Dict[str, Any]]:
        coll = get_reports_collection()
        cursor = coll.find({"project_id": project_id}).sort("created_at", -1)
        reports = []
        for r in cursor:
            rep = _serialize_doc(r)
            # Remove giant base64 payload from list view for network speed
            rep.pop("pdf_base64", None)
            reports.append(rep)
        return reports

    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        coll = get_reports_collection()
        doc = coll.find_one({"id": report_id})
        return _serialize_doc(doc)

    @staticmethod
    def update_report(report_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        coll = get_reports_collection()
        now = datetime.now(timezone.utc).isoformat()
        fields: Dict[str, Any] = {}

        for key in ["title", "executive_summary", "detailed_synthesis", "comparison_table", "research_gaps"]:
            if key in update_data and update_data[key] is not None:
                fields[key] = update_data[key]

        if not fields:
            return DatabaseService.get_report(report_id)

        fields["updated_at"] = now
        coll.update_one({"id": report_id}, {"$set": fields})
        return DatabaseService.get_report(report_id)

    @staticmethod
    def delete_report(report_id: str) -> bool:
        coll = get_reports_collection()
        rep = coll.find_one({"id": report_id})
        if rep and rep.get("pdf_path"):
            pdf_path = Path(rep["pdf_path"])
            if pdf_path.exists():
                try:
                    pdf_path.unlink()
                except OSError:
                    pass
        res = coll.delete_one({"id": report_id})
        return res.deleted_count > 0
