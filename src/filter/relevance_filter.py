import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from ..models.schemas import DiscoveredPage, FilterDecision
from ..config import Config

logger = logging.getLogger("ResearchLens.RelevanceFilter")


class RelevanceFilter:
    """Uses Groq API with structured output to score discovered pages and sections
    against the research topic and user instructions, keeping relevance scores and rejection reasons.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        threshold: float = Config.RELEVANCE_THRESHOLD
    ):
        self.api_key = api_key or Config.GROQ_API_KEY
        self.model_name = model_name or Config.GROQ_FILTER_MODEL
        self.threshold = threshold
        self.decisions_history: List[FilterDecision] = []

    def evaluate_candidates(
        self,
        candidates: List[DiscoveredPage],
        user_instructions: str,
        research_topic: Optional[str] = None
    ) -> List[DiscoveredPage]:
        """Evaluates a list of discovered pages, assigning scores and rejection reasons.
        Marks `selected = True` for candidates that meet or exceed the relevance threshold.
        """
        topic_context = research_topic or "Research Paper Topics and Evidence"
        selected_candidates: List[DiscoveredPage] = []

        for candidate in candidates:
            decision = self.evaluate_single_page(candidate, user_instructions, topic_context)
            self.decisions_history.append(decision)

            candidate.relevance_score = decision.relevance_score
            candidate.relevance_reason = decision.reason

            if decision.is_relevant:
                candidate.selected = True
                candidate.status = "evaluated_relevant"
                selected_candidates.append(candidate)
            else:
                candidate.selected = False
                candidate.status = "evaluated_rejected"

        logger.info(f"Filtering completed: {len(selected_candidates)}/{len(candidates)} candidates approved.")
        return selected_candidates

    def evaluate_single_page(
        self,
        candidate: DiscoveredPage,
        user_instructions: str,
        research_topic: str
    ) -> FilterDecision:
        """Evaluates a single candidate page using Groq structured JSON or heuristic fallback."""
        if not self.api_key or self.api_key.strip() == "":
            return self._heuristic_fallback(candidate, user_instructions, research_topic)

        prompt = f"""You are an expert research relevance evaluator for an AI research assistant.
Evaluate whether the following web page is relevant and valuable for the specified research topic and user instructions.

RESEARCH TOPIC:
{research_topic}

USER REPORT INSTRUCTIONS:
{user_instructions}

CANDIDATE PAGE INFORMATION:
- URL: {candidate.url}
- Title: {candidate.title or 'Unknown'}
- Snippet/Description: {candidate.snippet or 'No description available'}

CRITERIA:
1. Does this page discuss concepts, benchmarks, methodologies, or findings relevant to the research topic?
2. Does it help fulfill the user's instructions (e.g. gaps, comparison, empirical evidence)?
3. Reject navigation hubs, privacy policies, login screens, or unrelated marketing pages.

Provide your decision strictly as a valid JSON object matching this schema:
{{
  "relevance_score": <float between 0.0 and 10.0>,
  "is_relevant": <true if score >= {self.threshold} and truly useful, otherwise false>,
  "reason": "<Specific reason explaining why this page is accepted or rejected based on the content and instructions>",
  "key_topics_found": ["<topic1>", "<topic2>"]
}}
"""

        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research paper relevance evaluator. Output only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=400,
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            # Ensure URL is populated
            data["url"] = candidate.url
            if "is_relevant" not in data:
                data["is_relevant"] = float(data.get("relevance_score", 0)) >= self.threshold

            decision = FilterDecision(**data)
            return decision

        except Exception as e:
            logger.warning(f"Groq evaluation call failed for {candidate.url}: {e}. Using heuristic fallback.")
            return self._heuristic_fallback(candidate, user_instructions, research_topic)

    def _heuristic_fallback(
        self,
        candidate: DiscoveredPage,
        user_instructions: str,
        research_topic: str
    ) -> FilterDecision:
        """Intelligent heuristic scoring when Groq API key is absent or unavailable."""
        url_lower = candidate.url.lower()
        title_lower = (candidate.title or "").lower()
        snippet_lower = (candidate.snippet or "").lower()
        combined_text = f"{title_lower} {snippet_lower} {url_lower}"

        # Negative penalty terms (boilerplate/nav pages)
        reject_keywords = ["login", "signin", "signup", "terms", "privacy", "cookie", "contact", "about-us", "cart", "checkout"]
        if any(bad in url_lower for bad in reject_keywords):
            return FilterDecision(
                url=candidate.url,
                relevance_score=2.0,
                is_relevant=False,
                reason="Rejected: Page appears to be a boilerplate utility or navigation page (login/terms/privacy).",
                key_topics_found=[]
            )

        # Extract tokens from instructions and research topic
        import re
        tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", f"{research_topic} {user_instructions}".lower()))
        # Remove common stop words
        stopwords = {"this", "that", "with", "from", "have", "more", "focus", "research", "paper", "report", "under", "pages", "table"}
        meaningful_tokens = [t for t in tokens if t not in stopwords]

        matches = [t for t in meaningful_tokens if t in combined_text]
        score = 5.0  # Base neutral score

        if matches:
            score += min(len(matches) * 1.5, 4.5)
            reason = f"Accepted: Discovered page aligns with instructions and matches key topics: {', '.join(matches[:4])}."
            is_relevant = score >= self.threshold
        else:
            # Check if seed or root page
            if candidate.depth == 0:
                score = 7.5
                reason = "Accepted: Seed reference URL provided directly by user."
                is_relevant = True
            else:
                score = 4.5
                reason = "Rejected: Insufficient topical alignment with user instructions and research focus."
                is_relevant = False

        return FilterDecision(
            url=candidate.url,
            relevance_score=round(score, 1),
            is_relevant=is_relevant,
            reason=reason,
            key_topics_found=matches[:5]
        )

