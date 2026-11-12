import unittest
from src.scraper.state_machine import ScrapingStateMachine, CrawlState
from src.scraper.crawler import BoundedCrawler


class TestCrawlerAndStateMachine(unittest.TestCase):
    def test_state_machine_flow(self):
        sm = ScrapingStateMachine()
        self.assertEqual(sm.state, CrawlState.IDLE)

        sm.transition_to(CrawlState.INITIALIZING)
        self.assertEqual(sm.state, CrawlState.INITIALIZING)

        sm.transition_to(CrawlState.DISCOVERING)
        self.assertEqual(sm.state, CrawlState.DISCOVERING)

        sm.transition_to(CrawlState.FILTERING)
        self.assertEqual(sm.state, CrawlState.FILTERING)

        sm.transition_to(CrawlState.EXTRACTING)
        self.assertEqual(sm.state, CrawlState.EXTRACTING)

        sm.transition_to(CrawlState.COMPLETED)
        self.assertEqual(sm.state, CrawlState.COMPLETED)
        self.assertTrue(sm.is_terminal())

    def test_url_normalization_and_filtering(self):
        crawler = BoundedCrawler(max_depth=1, max_pages=5)

        norm = crawler._normalize_url("/abs/2312.10997#section1", "https://arxiv.org/list/cs/recent")
        self.assertEqual(norm, "https://arxiv.org/abs/2312.10997")

        # Non-http scheme rejected
        invalid = crawler._normalize_url("javascript:void(0)", "https://example.com")
        self.assertIsNone(invalid)


if __name__ == "__main__":
    unittest.main()

