import unittest
from bs4 import BeautifulSoup
from src.scraper.extractor import PageExtractor


class TestPageExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = PageExtractor()

    def test_clean_and_parse_html(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Research Paper: Advanced Modular RAG</title>
            <script>console.log("tracking script");</script>
            <style>body { font-size: 14px; }</style>
        </head>
        <body>
            <header><nav><a href="/home">Home</a></nav></header>
            <div class="cookie-banner">Accept cookies</div>
            <h1>Empirical Analysis of Modular RAG</h1>
            <p>Retrieval-Augmented Generation bridges knowledge cutoffs in foundation models.</p>
            <h2>Benchmark Results</h2>
            <p>Modular RAG demonstrated a 28.7% improvement in factual recall across test benchmarks.</p>
            <table>
                <tr><th>Model</th><th>F1</th></tr>
                <tr><td>Naive RAG</td><td>68.4</td></tr>
                <tr><td>Modular RAG</td><td>81.2</td></tr>
            </table>
            <footer><p>Copyright 2026 AI Research Lab</p></footer>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        result = self.extractor._clean_and_parse_html(
            url="https://arxiv.org/abs/2312.10997",
            soup=soup,
            status_code=200,
            method="requests_bs4"
        )

        self.assertEqual(result.title, "Research Paper: Advanced Modular RAG")
        self.assertIn("Empirical Analysis of Modular RAG", result.text)
        self.assertIn("Modular RAG demonstrated a 28.7% improvement", result.text)
        # Verify script, nav, cookie banner, and footer were stripped
        self.assertNotIn("tracking script", result.text)
        self.assertNotIn("Accept cookies", result.text)
        self.assertNotIn("Copyright 2026", result.text)
        # Verify table data conversion
        self.assertIn("[Table Data]:", result.text)
        self.assertIn("Naive RAG | 68.4", result.text)

    def test_requires_js_rendering_detection(self):
        # Empty SPA shell with root and noscript
        spa_html = """
        <html>
        <head><title>Dynamic React App</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
        </body>
        </html>
        """
        soup = BeautifulSoup(spa_html, "html.parser")
        self.assertTrue(self.extractor._requires_js_rendering(soup, spa_html))

        # Standard static HTML page
        static_html = "<html><body><h1>Title</h1><p>" + "Content paragraph here. " * 30 + "</p></body></html>"
        static_soup = BeautifulSoup(static_html, "html.parser")
        self.assertFalse(self.extractor._requires_js_rendering(static_soup, static_html))


if __name__ == "__main__":
    unittest.main()

