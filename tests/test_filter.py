import unittest
from src.filter.relevance_filter import RelevanceFilter
from src.models.schemas import DiscoveredPage


class TestRelevanceFilter(unittest.TestCase):
    def setUp(self):
        self.filter = RelevanceFilter(threshold=6.0)

    def test_relevance_evaluation(self):
        relevant_page = DiscoveredPage(
            url="https://arxiv.org/abs/2312.10997",
            title="Retrieval-Augmented Generation for Large Language Models: A Survey",
            snippet="Comprehensive survey detailing RAG paradigms, retrieval benchmarks, and research gaps.",
            depth=0
        )

        decision = self.filter.evaluate_single_page(
            candidate=relevant_page,
            user_instructions="Focus on research gaps and RAG benchmarks",
            research_topic="Retrieval-Augmented Generation"
        )

        self.assertTrue(decision.is_relevant)
        self.assertGreaterEqual(decision.relevance_score, 6.0)
        self.assertGreater(len(decision.reason), 0)

    def test_rejection_of_boilerplate(self):
        junk_page = DiscoveredPage(
            url="https://example.com/login?redirect=true",
            title="Sign In to Your Account",
            snippet="Please enter your email and password to log in.",
            depth=1
        )

        decision = self.filter.evaluate_single_page(
            candidate=junk_page,
            user_instructions="Focus on research gaps and RAG benchmarks",
            research_topic="Retrieval-Augmented Generation"
        )

        self.assertFalse(decision.is_relevant)
        self.assertLess(decision.relevance_score, 6.0)
        self.assertGreater(len(decision.reason), 0)


if __name__ == "__main__":
    unittest.main()

