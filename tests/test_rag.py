import unittest
from src.rag.embeddings import EmbeddingEngine
from src.rag.vector_store import VectorStore
from src.models.schemas import DocumentChunk, DocumentMetadata


class TestRAGPipeline(unittest.TestCase):
    def setUp(self):
        self.embedding_engine = EmbeddingEngine()
        self.vector_store = VectorStore(embedding_engine=self.embedding_engine)

    def test_embedding_and_retrieval(self):
        chunks = [
            DocumentChunk(
                chunk_id="chunk_1",
                text="Retrieval-Augmented Generation bridges knowledge gaps by querying vector databases with dense embeddings.",
                metadata=DocumentMetadata(
                    source_type="uploaded_document",
                    filename="rag_paper.pdf",
                    page=1,
                    section="Abstract"
                )
            ),
            DocumentChunk(
                chunk_id="chunk_2",
                text="Convolutional neural networks are widely used in computer vision for image classification and object detection.",
                metadata=DocumentMetadata(
                    source_type="uploaded_document",
                    filename="cv_paper.pdf",
                    page=5,
                    section="Methods"
                )
            ),
            DocumentChunk(
                chunk_id="chunk_3",
                text="Modular RAG architectures introduce routing, rewriting, and adaptive retrieval pipelines for complex queries.",
                metadata=DocumentMetadata(
                    source_type="web_scraped",
                    url="https://arxiv.org/abs/2312.10997",
                    title="Modular RAG Survey",
                    section="Modular Patterns"
                )
            )
        ]

        self.vector_store.add_chunks(chunks)
        self.assertEqual(len(self.vector_store.get_all_chunks()), 3)

        # Query specifically about RAG and retrieval
        query = "How does Modular RAG routing and retrieval work?"
        results = self.vector_store.similarity_search(query=query, top_k=2)

        self.assertEqual(len(results), 2)
        # Verify that score is attached and positive
        self.assertIsNotNone(results[0].score)
        self.assertGreater(results[0].score, 0)
        # Results should contain RAG chunks
        found_sources = [r.metadata.source_type for r in results]
        self.assertTrue("uploaded_document" in found_sources or "web_scraped" in found_sources)


if __name__ == "__main__":
    unittest.main()

