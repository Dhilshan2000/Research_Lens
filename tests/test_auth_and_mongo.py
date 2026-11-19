import unittest
import uuid
from starlette.testclient import TestClient
from src.server import app
from src.database.db import DatabaseService, init_db
from src.database.mongo import (
    get_users_collection,
    get_projects_collection,
    get_documents_collection,
    get_reports_collection,
    get_configurations_collection
)


class TestAuthAndMongoCRUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_user_registration_and_jwt(self):
        unique_suffix = str(uuid.uuid4())[:8]
        username = f"testuser_{unique_suffix}"
        email = f"test_{unique_suffix}@example.com"
        password = "SecurePassword123!"

        # 1. Register new user
        reg_payload = {
            "username": username,
            "email": email,
            "password": password
        }
        res = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["username"], username)
        self.assertEqual(data["user"]["email"], email)
        token = data["access_token"]

        # 2. Duplicate registration should fail (400)
        res_dup = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res_dup.status_code, 400)

        # 3. Login with credentials
        login_payload = {
            "username": username,
            "password": password
        }
        res_login = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res_login.status_code, 200)
        login_data = res_login.json()
        self.assertIn("access_token", login_data)

        # 4. Login with wrong password should fail (401)
        res_wrong = self.client.post("/api/auth/login", json={"username": username, "password": "WrongPassword"})
        self.assertEqual(res_wrong.status_code, 401)

        # 5. Access /api/auth/me with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        res_me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res_me.status_code, 200)
        me_data = res_me.json()
        self.assertEqual(me_data["username"], username)
        self.assertEqual(me_data["email"], email)

        # 6. Access /api/auth/me without token should fail (401)
        res_unauth = self.client.get("/api/auth/me")
        self.assertEqual(res_unauth.status_code, 401)

    def test_02_mongodb_collections_crud(self):
        # 1. Test Project creation & storage in MongoDB
        project_data = {
            "title": "Mongo CRUD Test Project",
            "topic": "Neural Information Retrieval",
            "directives": "Focus on dense retrieval latency",
            "preset": "Standard Brief",
            "model": "llama-3.3-70b-versatile",
            "crawl_depth": 2,
            "max_pages": 10,
            "same_domain": True,
            "relevance_threshold": 6.5,
            "top_k": 4,
            "chunk_size": 500,
            "chunk_overlap": 80,
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "seed_urls": ["https://arxiv.org/abs/2312.10997"]
        }
        created_proj = DatabaseService.create_project(project_data)
        proj_id = created_proj["id"]
        self.assertIsNotNone(proj_id)

        # Verify in native collection
        proj_in_db = get_projects_collection().find_one({"id": proj_id})
        self.assertIsNotNone(proj_in_db)
        self.assertEqual(proj_in_db["title"], "Mongo CRUD Test Project")

        # 2. Test Configurations collection
        config_in_db = get_configurations_collection().find_one({"project_id": proj_id})
        self.assertIsNotNone(config_in_db)
        self.assertEqual(config_in_db["embedding_model"], "BAAI/bge-small-en-v1.5")

        # Update configuration via DatabaseService
        DatabaseService.save_configuration(proj_id, {"chunk_size": 750, "model": "openai/gpt-oss-120b"})
        updated_config = DatabaseService.get_configuration(proj_id)
        self.assertEqual(updated_config["chunk_size"], 750)
        self.assertEqual(updated_config["model"], "openai/gpt-oss-120b")

        # 3. Test Configuration REST API endpoints
        res_cfg_get = self.client.get(f"/api/projects/{proj_id}/configuration")
        self.assertEqual(res_cfg_get.status_code, 200)
        self.assertEqual(res_cfg_get.json()["chunk_size"], 750)

        res_cfg_put = self.client.put(f"/api/projects/{proj_id}/configuration", json={"chunk_size": 900})
        self.assertEqual(res_cfg_put.status_code, 200)
        self.assertEqual(res_cfg_put.json()["chunk_size"], 900)

        # 4. Test Documents collection CRUD
        doc_entry = DatabaseService.add_document(
            project_id=proj_id,
            filename="sample_retrieval.pdf",
            file_type="pdf",
            file_size=2048,
            file_path="data/uploads/sample_retrieval.pdf",
            parsed_chunks_count=12
        )
        doc_id = doc_entry["id"]
        self.assertIsNotNone(doc_id)

        # Check documents collection
        docs = DatabaseService.get_documents(proj_id)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["filename"], "sample_retrieval.pdf")

        # 5. Test Reports collection CRUD (with PDF base64 storage)
        sample_report_data = {
            "title": "Synthesis Report on Neural IR",
            "executive_summary": "Neural IR models demonstrate strong dense retrieval recall.",
            "detailed_synthesis": "Comprehensive overview of bi-encoders and cross-encoders.",
            "comparison_table": [{"dimension": "Latency", "uploaded_findings": "12ms", "web_findings": "15ms", "synthesis": "Comparable"}],
            "research_gaps": ["Out of domain generalization is limited."],
            "citations": [],
            "model_used": "llama-3.3-70b-versatile"
        }
        report_entry = DatabaseService.create_report(proj_id, sample_report_data)
        report_id = report_entry["id"]
        self.assertIsNotNone(report_id)

        # Check reports collection
        reports_list = DatabaseService.get_reports(proj_id)
        self.assertEqual(len(reports_list), 1)
        self.assertEqual(reports_list[0]["title"], "Synthesis Report on Neural IR")

        # Read specific report
        single_report = DatabaseService.get_report(report_id)
        self.assertEqual(single_report["id"], report_id)

        # 6. Delete cascade test
        del_success = DatabaseService.delete_project(proj_id)
        self.assertTrue(del_success)

        # Verify cascading deletion across all collections
        self.assertIsNone(get_projects_collection().find_one({"id": proj_id}))
        self.assertEqual(get_documents_collection().count_documents({"project_id": proj_id}), 0)
        self.assertEqual(get_reports_collection().count_documents({"project_id": proj_id}), 0)
        self.assertEqual(get_configurations_collection().count_documents({"project_id": proj_id}), 0)


if __name__ == "__main__":
    unittest.main()
