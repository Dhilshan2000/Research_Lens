import unittest
from pathlib import Path

from src.parsers.document_parser import DocumentParser
from src.scraper.extractor import PageExtractor
from src.filter.relevance_filter import RelevanceFilter
from src.models.schemas import DiscoveredPage, ScrapedPageContent
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingEngine
from src.rag.vector_store import VectorStore
from src.synthesizer.groq_synthesizer import GroqSynthesizer
from src.exporter.pdf_generator import PDFReportGenerator


class TestEndToEndPipeline(unittest.TestCase):
    def test_full_pipeline_flow(self):
        # 1. Parse Sample Research Files
        sample_txt = Path(__file__).resolve().parent.parent / "data" / "samples" / "rag_modular_survey.txt"
        sample_csv = Path(__file__).resolve().parent.parent / "data" / "samples" / "rag_benchmarks.csv"

        parsed_items = []
        if sample_txt.exists():
            parsed_items.extend(DocumentParser.parse_file(str(sample_txt)))
        if sample_csv.exists():
            parsed_items.extend(DocumentParser.parse_file(str(sample_csv)))

        self.assertGreater(len(parsed_items), 0)

        # 2. Web Evidence Discovery & Relevance Filtering
        candidate = DiscoveredPage(
            url="https://arxiv.org/abs/2312.10997",
            title="Retrieval-Augmented Generation for Large Language Models: A Survey",
            snippet="Detailed overview of Naive, Advanced, and Modular RAG paradigms, evaluations, and research gaps.",
            depth=0
        )
        rel_filter = RelevanceFilter(threshold=6.0)
        selected_candidates = rel_filter.evaluate_candidates(
            candidates=[candidate],
            user_instructions="Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages.",
            research_topic="Retrieval-Augmented Generation"
        )
        self.assertEqual(len(selected_candidates), 1)

        # Simulated extracted content
        scraped_web = [
            ScrapedPageContent(
                url=candidate.url,
                title=candidate.title,
                text="Advanced RAG introduces iterative retrieval, dynamic query routing, and context compression to solve high noise.\n\nRecent benchmarks show latency tradeoffs and multimodal gaps.",
                cleaned_sections=[
                    {"heading": "Evaluation Benchmarks", "content": "RGB, RECALL, and CRUD are standard benchmarks for evaluating RAG robustness."},
                    {"heading": "Research Gaps", "content": "Knowledge conflicts between parametric memory and non-parametric retrieved documents remain an unresolved challenge."}
                ],
                extraction_method="requests_bs4",
                status_code=200,
                metadata={"domain": "arxiv.org"}
            )
        ]

        # 3. Chunking with Metadata
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
        doc_chunks = chunker.chunk_document_items(parsed_items)
        web_chunks = chunker.chunk_scraped_pages(scraped_web)
        all_chunks = doc_chunks + web_chunks

        self.assertGreater(len(all_chunks), 2)
        # Verify both types present
        types = {c.metadata.source_type for c in all_chunks}
        self.assertIn("uploaded_document", types)
        self.assertIn("web_scraped", types)

        # 4. Vector Store & Semantic Retrieval
        vector_store = VectorStore(embedding_engine=EmbeddingEngine())
        vector_store.add_chunks(all_chunks)

        query = "What are the major research gaps in modular RAG architectures and tabular reasoning?"
        retrieved = vector_store.similarity_search(query=query, top_k=5)
        self.assertEqual(len(retrieved), min(5, len(all_chunks)))
        for r in retrieved:
            self.assertIsNotNone(r.score)

        # 5. Grounded Synthesizer
        synthesizer = GroqSynthesizer()
        report = synthesizer.synthesize(
            retrieved_chunks=retrieved,
            user_instructions="Focus on research gaps, use an academic tone, add a comparison table, and keep the report under four pages.",
            research_topic="Modular RAG Architectures & Tabular Gaps"
        )

        self.assertTrue(len(report.title) > 0)
        self.assertTrue(len(report.executive_summary) > 0)
        self.assertIsNotNone(report.comparison_table)
        self.assertGreater(len(report.citations), 0)

        # 6. PDF Generation
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_pdf(report)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 2000)


if __name__ == "__main__":
    unittest.main()

