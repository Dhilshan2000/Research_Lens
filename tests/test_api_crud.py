import unittest
import io
from pathlib import Path
from starlette.testclient import TestClient
from src.server import app
from src.database.db import init_db

class TestApiCRUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_health_and_meta(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")

        res_models = self.client.get("/api/models")
        self.assertEqual(res_models.status_code, 200)
        self.assertIn("models", res_models.json())

        res_presets = self.client.get("/api/presets")
        self.assertEqual(res_presets.status_code, 200)
        self.assertGreater(len(res_presets.json()), 0)

    def test_project_crud_lifecycle(self):
        # 1. Create Project
        create_payload = {
            "title": "API Test Project",
            "topic": "Graph RAG Trade-offs",
            "directives": "Focus on latency",
            "preset": "Standard Brief",
            "model": "openai/gpt-oss-120b",
            "seed_urls": ["https://arxiv.org/abs/2312.10997"],
            "crawl_depth": 1,
            "max_pages": 5
        }
        res_create = self.client.post("/api/projects", json=create_payload)
        self.assertEqual(res_create.status_code, 201)
        project = res_create.json()
        self.assertIn("id", project)
        proj_id = project["id"]
        self.assertEqual(project["title"], "API Test Project")

        # 2. Read Project
        res_get = self.client.get(f"/api/projects/{proj_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["topic"], "Graph RAG Trade-offs")

        # 3. List Projects
        res_list = self.client.get("/api/projects?search=API+Test")
        self.assertEqual(res_list.status_code, 200)
        self.assertGreater(len(res_list.json()), 0)

        # 4. Update Project
        update_payload = {
            "title": "Updated API Test Project",
            "topic": "Updated Topic"
        }
        res_update = self.client.put(f"/api/projects/{proj_id}", json=update_payload)
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["title"], "Updated API Test Project")

        # 5. Delete Project
        res_del = self.client.delete(f"/api/projects/{proj_id}")
        self.assertEqual(res_del.status_code, 200)

        # Confirm 404 after delete
        res_check = self.client.get(f"/api/projects/{proj_id}")
        self.assertEqual(res_check.status_code, 404)

    def test_report_generation_api(self):
        # 1. Create Project
        create_payload = {
            "title": "Report Generation Test",
            "topic": "Modular RAG Architectures",
            "directives": "Include comparison table and research gaps",
            "preset": "Standard Brief",
            "model": "openai/gpt-oss-120b",
            "seed_urls": [],
            "top_k": 3
        }
        res_proj = self.client.post("/api/projects", json=create_payload)
        self.assertEqual(res_proj.status_code, 201)
        proj_id = res_proj.json()["id"]

        try:
            # 2. Upload sample text document
            file_content = b"# Modular RAG Overview\nModular RAG incorporates specialized modules for retrieval, routing, and synthesis.\nRecent evaluations on RGB benchmarks show 84.5% recall."
            files = [("files", ("test_modular_rag.txt", io.BytesIO(file_content), "text/plain"))]
            res_upload = self.client.post(f"/api/projects/{proj_id}/documents", files=files)
            self.assertEqual(res_upload.status_code, 200)
            self.assertEqual(len(res_upload.json()), 1)

            # 3. Trigger Report Generation
            res_gen = self.client.post(f"/api/projects/{proj_id}/generate-report")
            self.assertEqual(res_gen.status_code, 200)
            report = res_gen.json()
            self.assertIn("id", report)
            self.assertTrue(len(report["title"]) > 0)
            self.assertTrue(len(report["executive_summary"]) > 0)
            self.assertTrue(len(report["detailed_synthesis"]) > 0)
            self.assertIn("comparison_table", report)
            self.assertIn("citations", report)
            report_id = report["id"]

            # 4. Test PDF download endpoint
            res_pdf = self.client.get(f"/api/reports/{report_id}/pdf")
            self.assertEqual(res_pdf.status_code, 200)
            self.assertTrue(res_pdf.content.startswith(b"%PDF"))

        finally:
            # Cleanup project
            self.client.delete(f"/api/projects/{proj_id}")

if __name__ == "__main__":
    unittest.main()
