import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from ..models.schemas import ScrapedPageContent
from ..config import Config

logger = logging.getLogger("ResearchLens.Extractor")


class PageExtractor:
    """Extracts, cleans, and normalizes content from web pages using Requests + BeautifulSoup,
    with automatic detection for JavaScript-rendered SPAs.
    """

    def __init__(self, timeout: int = Config.CRAWL_TIMEOUT_SECONDS, user_agent: str = Config.USER_AGENT):
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def extract(self, url: str) -> ScrapedPageContent:
        """Fetches and extracts clean, normalized content from the given URL."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            status_code = response.status_code
        except Exception as e:
            logger.warning(f"Failed to fetch {url} via requests: {e}")
            return ScrapedPageContent(
                url=url,
                title="Failed to Load",
                text=f"Error extracting URL {url}: {str(e)}",
                status_code=500,
                extraction_method="failed"
            )

        soup = BeautifulSoup(html, "html.parser")

        # Check if page is an empty JS-rendered SPA that needs JS rendering
        if self._requires_js_rendering(soup, html):
            logger.info(f"Page {url} requires JS rendering. Attempting fallback...")
            js_content = self._try_js_rendering(url)
            if js_content:
                return js_content

        # Standard extraction with BeautifulSoup
        return self._clean_and_parse_html(url, soup, status_code, method="requests_bs4")

    def _requires_js_rendering(self, soup: BeautifulSoup, html: str) -> bool:
        """Heuristic check for client-rendered applications (React/Vue/Angular empty shells)."""
        body = soup.find("body")
        if not body:
            return True

        text_length = len(body.get_text(strip=True))
        has_js_indicators = bool(
            soup.find("noscript") or
            soup.find(id=re.compile(r"^(root|app|__next)$")) or
            "You need to enable JavaScript" in html or
            "Please turn on JavaScript" in html
        )

        return text_length < 250 and has_js_indicators

    def _try_js_rendering(self, url: str) -> Optional[ScrapedPageContent]:
        """Attempt to render via Playwright or Selenium if available."""
        import importlib
        # Try Playwright
        try:
            playwright_module = importlib.import_module("playwright.sync_api")
            sync_playwright = getattr(playwright_module, "sync_playwright")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(self.timeout * 1000)
                page.goto(url, wait_until="networkidle")
                rendered_html = page.content()
                browser.close()

                soup = BeautifulSoup(rendered_html, "html.parser")
                return self._clean_and_parse_html(url, soup, 200, method="playwright")
        except Exception as e:
            logger.debug(f"Playwright rendering not available or failed: {e}")

        # Try Selenium
        try:
            selenium_webdriver = importlib.import_module("selenium.webdriver")
            selenium_options = importlib.import_module("selenium.webdriver.chrome.options")
            options = selenium_options.Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            driver = selenium_webdriver.Chrome(options=options)
            driver.set_page_load_timeout(self.timeout)
            driver.get(url)
            rendered_html = driver.page_source
            driver.quit()

            soup = BeautifulSoup(rendered_html, "html.parser")
            return self._clean_and_parse_html(url, soup, 200, method="selenium")
        except Exception as e:
            logger.debug(f"Selenium rendering not available or failed: {e}")

        return None

    def _clean_and_parse_html(self, url: str, soup: BeautifulSoup, status_code: int, method: str) -> ScrapedPageContent:
        """Removes boilerplate elements and normalizes text and section headings."""
        # Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        else:
            parsed = urlparse(url)
            title = parsed.path.strip("/").split("/")[-1] or parsed.netloc

        # Remove clutter
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "svg", "noscript", "iframe"]):
            tag.decompose()

        # Remove common ad/cookie classes
        for tag in soup.find_all(class_=re.compile(r"(cookie|banner|ad-|advert|popup|modal|share-buttons)", re.IGNORECASE)):
            tag.decompose()

        # Extract headings
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4"]) if h.get_text(strip=True)]

        # Extract structured sections
        cleaned_sections: List[Dict[str, str]] = []
        current_heading = "Overview"
        current_paragraphs: List[str] = []

        # Convert tables to text before extracting paragraphs
        for table in soup.find_all("table"):
            table_rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if any(cells):
                    table_rows.append(" | ".join(cells))
            if table_rows:
                table_text = "\n".join(table_rows)
                new_p = soup.new_tag("p")
                new_p.string = f"\n[Table Data]:\n{table_text}\n"
                table.replace_with(new_p)

        for element in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            tag_name = element.name.lower()
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue

            if tag_name in ["h1", "h2", "h3"]:
                if current_paragraphs:
                    cleaned_sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_paragraphs)
                    })
                    current_paragraphs = []
                current_heading = text
            else:
                if len(text) > 20:  # Skip tiny noise
                    current_paragraphs.append(text)

        if current_paragraphs:
            cleaned_sections.append({
                "heading": current_heading,
                "content": "\n".join(current_paragraphs)
            })

        # Full normalized text
        full_text = "\n\n".join(
            f"### {sec['heading']}\n{sec['content']}" for sec in cleaned_sections
        ) if cleaned_sections else soup.get_text(separator="\n", strip=True)

        # Normalize excess whitespace
        full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()

        return ScrapedPageContent(
            url=url,
            title=title,
            headings=headings[:15],
            text=full_text,
            cleaned_sections=cleaned_sections,
            extraction_method=method,
            status_code=status_code,
            metadata={"domain": urlparse(url).netloc, "char_count": len(full_text)}
        )

