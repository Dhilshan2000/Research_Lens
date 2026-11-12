import unittest
import tempfile
import os
from src.parsers.document_parser import DocumentParser


class TestDocumentParser(unittest.TestCase):
    def test_parse_txt(self):
        content = """# Section 1: Overview
Retrieval-Augmented Generation (RAG) is a technique for enhancing LLM outputs.

## Section 2: Methodology
The system indexes documents using dense vector embeddings and retrieves top-k chunks.
"""
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            items = DocumentParser.parse_file(temp_path, original_filename="test_notes.txt")
            self.assertGreater(len(items), 0)
            self.assertEqual(items[0].filename, "test_notes.txt")
            self.assertEqual(items[0].file_type, "txt")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_parse_csv(self):
        csv_data = """Model,Recall@5,Latency_ms,F1_Score
Naive RAG,71.2,120,68.4
Modular RAG,84.5,195,81.2
Graph RAG,88.1,310,85.6
"""
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_data)
            temp_path = f.name

        try:
            items = DocumentParser.parse_file(temp_path, original_filename="benchmarks.csv")
            self.assertGreater(len(items), 0)
            self.assertEqual(items[0].filename, "benchmarks.csv")
            self.assertEqual(items[0].file_type, "csv")
            self.assertIn("benchmarks.csv", items[0].text)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()

