import unittest
from src.models.schemas import ResearchReport, SynthesisSection, ComparisonRow, Citation
from src.exporter.pdf_generator import PDFReportGenerator


class TestPDFGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = PDFReportGenerator()

    def test_pdf_generation(self):
        report = ResearchReport(
            title="Comparative Analysis of Modular RAG Frameworks",
            executive_summary="This report synthesizes empirical findings on RAG systems, contrasting uploaded benchmark documents with web evidence.",
            instructions_applied="Focus on research gaps, use academic tone, add comparison table, under 4 pages.",
            sections=[
                SynthesisSection(
                    title="1. Retrieval Architectures & Trade-offs",
                    content="Naive RAG pipelines suffer from low precision and hallucinations [1]. In contrast, modular frameworks incorporate adaptive query routing [2].",
                    citations=[1, 2]
                )
            ],
            comparison_table=[
                ComparisonRow(
                    dimension="Retrieval Accuracy",
                    uploaded_findings="Dense retrieval achieves 78.4% top-5 recall on MS-MARCO [1].",
                    web_findings="Hybrid sparse-dense retrieval reaches 84.1% on recent benchmarks [2].",
                    synthesis="Hybrid indexes significantly mitigate out-of-vocabulary limitations."
                )
            ],
            research_gaps=[
                "Lack of standardized evaluation for multi-hop reasoning over unstructured web tables [1].",
                "High latency overhead incurred during dynamic query reformulation in modular RAG [2]."
            ],
            citations=[
                Citation(
                    citation_id=1,
                    source_type="uploaded_document",
                    source_label="rag_benchmark.pdf (Page 4)",
                    url_or_file="rag_benchmark.pdf",
                    page_or_section="Page 4",
                    snippet="Dense retrieval achieves 78.4% top-5 recall."
                ),
                Citation(
                    citation_id=2,
                    source_type="web_evidence",
                    source_label="RAG Survey 2024 (https://arxiv.org/abs/2312.10997)",
                    url_or_file="https://arxiv.org/abs/2312.10997",
                    title="RAG Survey 2024",
                    snippet="Hybrid sparse-dense retrieval reaches 84.1%."
                )
            ]
        )

        pdf_bytes = self.generator.generate_pdf(report)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)
        # PDF files start with %PDF
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()

