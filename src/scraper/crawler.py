import time
import logging
from typing import List, Set, Dict, Optional, Callable
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

from ..models.schemas import DiscoveredPage, ScrapedPageContent
from .state_machine import ScrapingStateMachine, CrawlState
from .extractor import PageExtractor
from ..config import Config

logger = logging.getLogger("ResearchLens.Crawler")


class BoundedCrawler:
    """Agent that performs bounded crawling starting strictly from user-supplied reference URLs.
    Collects links, titles, and snippets first (Discovery phase) without full extraction.
    Respects domain bounds, crawl depth, max page count, and robots.txt.
    """

    def __init__(
        self,
        max_depth: int = Config.DEFAULT_CRAWL_DEPTH,
        max_pages: int = Config.DEFAULT_MAX_PAGES,
        same_domain_only: bool = True,
        timeout: int = Config.CRAWL_TIMEOUT_SECONDS,
        user_agent: str = Config.USER_AGENT,
        state_machine: Optional[ScrapingStateMachine] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self.timeout = timeout
        self.user_agent = user_agent
        self.state_machine = state_machine or ScrapingStateMachine()
        self.progress_callback = progress_callback
        self.extractor = PageExtractor(timeout=timeout, user_agent=user_agent)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self._robots_cache: Dict[str, RobotFileParser] = {}

    def _normalize_url(self, raw_url: str, base_url: str) -> Optional[str]:
        """Normalizes URLs, strips fragments, and filters out non-HTTP schemes."""
        try:
            absolute = urljoin(base_url, raw_url)
            clean_url, _ = urldefrag(absolute)
            parsed = urlparse(clean_url)
            if parsed.scheme not in ["http", "https"]:
                return None
            # Standardize by lowercasing domain and removing trailing slash if path is not root
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
            normalized = f"{parsed.scheme}://{netloc}{path}"
            if parsed.query:
                normalized += f"?{parsed.query}"
            return normalized
        except Exception:
            return None

    def _can_fetch(self, url: str) -> bool:
        """Checks robots.txt for the given URL."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in self._robots_cache:
            rp = RobotFileParser()
            robots_url = f"{domain}/robots.txt"
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                pass
            self._robots_cache[domain] = rp
        return self._robots_cache[domain].can_fetch(self.user_agent, url)

    def discover_candidates(self, seed_urls: List[str]) -> List[DiscoveredPage]:
        """Discovery phase: Discovers candidate pages without performing full extraction."""
        self.state_machine.transition_to(CrawlState.INITIALIZING, {"seed_urls": seed_urls})

        valid_seeds: List[str] = []
        allowed_domains: Set[str] = set()

        for s in seed_urls:
            s = s.strip()
            if not s:
                continue
            if not s.startswith("http://") and not s.startswith("https://"):
                s = "https://" + s
            norm = self._normalize_url(s, s)
            if norm:
                valid_seeds.append(norm)
                allowed_domains.add(urlparse(norm).netloc.lower())

        if not valid_seeds:
            self.state_machine.fail("No valid seed URLs provided.")
            return []

        self.state_machine.transition_to(CrawlState.DISCOVERING, {
            "valid_seeds": valid_seeds,
            "allowed_domains": list(allowed_domains)
        })

        candidates: List[DiscoveredPage] = []
        visited: Set[str] = set()
        queue: List[Dict[str, Any]] = [{"url": seed, "depth": 0, "parent": None} for seed in valid_seeds]

        while queue and len(candidates) < self.max_pages:
            current = queue.pop(0)
            url = current["url"]
            depth = current["depth"]
            parent = current["parent"]

            if url in visited:
                continue
            visited.add(url)

            if not self._can_fetch(url):
                logger.info(f"Skipping {url} due to robots.txt restrictions.")
                continue

            if self.progress_callback:
                self.progress_callback(f"Discovering candidate: {url}", len(candidates), self.max_pages)

            # Shallow fetch to get title, snippet, and child links
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                title = ""
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
                elif soup.find("h1"):
                    title = soup.find("h1").get_text(strip=True)
                else:
                    title = url

                # Snippet from meta description or first paragraph
                snippet = ""
                meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                if meta_desc and meta_desc.get("content"):
                    snippet = meta_desc["content"].strip()
                elif soup.find("p"):
                    snippet = soup.find("p").get_text(strip=True)[:250]

                page_item = DiscoveredPage(
                    url=url,
                    title=title,
                    snippet=snippet,
                    parent_url=parent,
                    depth=depth,
                    status="discovered"
                )
                candidates.append(page_item)

                # Collect child links if depth < max_depth
                if depth < self.max_depth and len(candidates) + len(queue) < self.max_pages * 2:
                    for a in soup.find_all("a", href=True):
                        raw_href = a["href"].strip()
                        child_url = self._normalize_url(raw_href, url)
                        if not child_url or child_url in visited:
                            continue

                        child_domain = urlparse(child_url).netloc.lower()
                        if self.same_domain_only and child_domain not in allowed_domains:
                            continue

                        # Avoid non-content extensions
                        if any(child_url.lower().endswith(ext) for ext in [".jpg", ".png", ".gif", ".zip", ".tar", ".mp4", ".mp3", ".css", ".js"]):
                            continue

                        queue.append({
                            "url": child_url,
                            "depth": depth + 1,
                            "parent": url
                        })

                # Polite crawl delay
                time.sleep(0.1)

            except Exception as e:
                logger.warning(f"Error discovering {url}: {e}")
                continue

        logger.info(f"Discovery completed with {len(candidates)} candidate pages.")
        return candidates

    def extract_selected(self, selected_candidates: List[DiscoveredPage]) -> List[ScrapedPageContent]:
        """Extraction phase: Extracts full clean content for LLM-approved candidate pages."""
        self.state_machine.transition_to(CrawlState.EXTRACTING, {
            "selected_count": len(selected_candidates)
        })

        results: List[ScrapedPageContent] = []
        total = len(selected_candidates)

        for idx, page in enumerate(selected_candidates):
            if self.progress_callback:
                self.progress_callback(f"Extracting content ({idx+1}/{total}): {page.url}", idx + 1, total)

            try:
                content = self.extractor.extract(page.url)
                if content.status_code == 200 and len(content.text) > 100:
                    page.status = "extracted"
                    results.append(content)
                else:
                    page.status = "failed"
            except Exception as e:
                logger.warning(f"Extraction failed for {page.url}: {e}")
                page.status = "failed"

        self.state_machine.transition_to(CrawlState.COMPLETED, {
            "extracted_count": len(results)
        })
        return results

