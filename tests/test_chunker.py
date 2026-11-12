import unittest
from src.rag.chunker import DocumentChunker
from src.parsers.document_parser import ParsedDocumentItem
from src.models.schemas import ScrapedPageContent


class TestDocumentChunker(unittest.TestCase):
    def setUp(self):
        self.chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

    def test_token_counting(self):
        text = "Retrieval-Augmented Generation improves large language models by grounding answers."
        tokens = self.chunker.count_tokens(text)
        self.assertGreater(tokens, 5)

    def test_chunk_document_items_metadata_retention(self):
        parsed = [
            ParsedDocumentItem(
                text="This is a test research document on RAG architecture.\n\n" * 20,
                filename="rag_survey.pdf",
                file_type="pdf",
                page=3,
                total_pages=10,
                section="Section 2: Architecture"
            )
        ]

        chunks = self.chunker.chunk_document_items(parsed)
        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertEqual(chunk.metadata.source_type, "uploaded_document")
            self.assertEqual(chunk.metadata.filename, "rag_survey.pdf")
            self.assertEqual(chunk.metadata.page, 3)
            self.assertEqual(chunk.metadata.section, "Section 2: Architecture")
            self.assertGreater(chunk.token_count, 0)

    def test_chunk_scraped_pages_metadata_retention(self):
        pages = [
            ScrapedPageContent(
                url="https://arxiv.org/abs/2312.10997",
                title="Retrieval-Augmented Generation for Large Language Models: A Survey",
                text="A comprehensive survey on RAG paradigms including Naive, Advanced, and Modular RAG.\n\n" * 15,
                cleaned_sections=[{
                    "heading": "Paradigms of RAG",
                    "content": "Naive RAG follows retrieve-then-read. Advanced RAG incorporates pre-retrieval and post-retrieval."
                }],
                extraction_method="requests_bs4",
                status_code=200,
                metadata={"domain": "arxiv.org"}
            )
        ]

        chunks = self.chunker.chunk_scraped_pages(pages)
        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertEqual(chunk.metadata.source_type, "web_scraped")
            self.assertEqual(chunk.metadata.url, "https://arxiv.org/abs/2312.10997")
            self.assertEqual(chunk.metadata.title, "Retrieval-Augmented Generation for Large Language Models: A Survey")


if __name__ == "__main__":
    unittest.main()

