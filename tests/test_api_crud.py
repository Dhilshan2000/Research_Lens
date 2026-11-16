import unittest
import json
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

if __name__ == "__main__":
    unittest.main()
