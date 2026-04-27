"""
NewsAPI Ingestor — Focused on AI launch events from major companies.
Covers tech launches, marketing AI, and finance AI — user's core domains.
"""
import logging
from datetime import datetime, timezone, timedelta

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"

# Five focused queries — each targets a specific domain
# Consolidated to stay well within the 100 req/day free tier
SEARCH_QUERIES = [
    # 1. Top company launches and model releases
    '(OpenAI OR Anthropic OR "Google DeepMind" OR "Meta AI" OR xAI OR Grok OR Gemini OR Claude OR ChatGPT) AND (launch OR release OR announce OR update OR new)',
    # 2. Microsoft, Amazon, Nvidia, GitHub AI news
    '(Microsoft OR Amazon OR AWS OR Nvidia OR GitHub) AND (AI OR artificial intelligence) AND (launch OR release OR update OR announce)',
    # 3. New AI models, agents and tools
    '("AI model" OR "AI agent" OR "large language model" OR LLM OR chatbot) AND (launch OR release OR new OR announce)',
    # 4. Marketing AI — user's domain
    '("AI marketing" OR "generative AI" OR "AI tools") AND (marketing OR advertising OR content)',
    # 5. Finance AI — user's domain
    '("AI finance" OR "AI trading" OR "fintech" OR "AI banking") AND (launch OR announce OR deploy OR raise OR funding)',
]

# Only include articles about these companies for top-priority alerting
TOP_COMPANY_PATTERNS = [
    "openai", "anthropic", "google deepmind", "deepmind", "meta ai",
    "microsoft", "amazon", "aws", "nvidia", "apple", "github",
    "mistral", "cohere", "perplexity", "xai", "grok", "elon musk",
    "stability ai", "hugging face", "langchain", "gemini", "google gemini",
]

LAUNCH_KEYWORDS = [
    "launch", "release", "announce", "introduce", "unveil",
    "new model", "new agent", "available", "update", "upgrade",
    "open source", "funding", "acqui", "partnership",
]


class NewsAPIIngestor:
    def __init__(self):
        self.client = httpx.Client(timeout=20.0)
        self.api_key = settings.NEWS_API_KEY

    def _is_top_company(self, title: str, description: str) -> bool:
        text = f"{title} {description}".lower()
        return any(co in text for co in TOP_COMPANY_PATTERNS)

    def _is_launch(self, title: str, description: str) -> bool:
        text = f"{title} {description}".lower()
        return any(kw in text for kw in LAUNCH_KEYWORDS)

    def _fetch_query(self, query: str) -> list[dict]:
        if not self.api_key:
            return []

        # Look back 48 hours — capture more fresh events
        from_date = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 20,
            "apiKey": self.api_key,
        }

        try:
            resp = self.client.get(NEWS_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "ok":
                logger.warning("NewsAPI error: %s", data.get("message", "unknown"))
                return []
        except Exception as e:
            logger.warning("NewsAPI request failed: %s", e)
            return []

        entries = []
        for article in data.get("articles", []):
            title = (article.get("title") or "").strip()
            description = (article.get("description") or "").strip()
            url = article.get("url", "")
            published_at = article.get("publishedAt", "")
            source_name = article.get("source", {}).get("name", "NewsAPI")

            if not title or not url or title == "[Removed]":
                continue
            # Skip if not about AI at all
            if "ai" not in f"{title} {description}".lower():
                continue

            # Parse timestamp
            try:
                ts = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                ).isoformat()
            except Exception:
                ts = "1970-01-01T00:00:00+00:00"

            is_top_co = self._is_top_company(title, description)
            is_launch = self._is_launch(title, description)

            entries.append({
                "title": title[:300],
                "company": source_name,
                "summary": description[:500],
                "timestamp": ts,
                "source_url": url,
                "source_name": "newsapi",
                "is_launch": is_launch,
                "is_top_company": is_top_co,
            })

        return entries

    def ingest(self) -> list[dict]:
        if not self.api_key:
            logger.warning("NEWS_API_KEY not set — skipping NewsAPI ingestion")
            return []

        all_entries = []
        for query in SEARCH_QUERIES:
            entries = self._fetch_query(query)
            logger.info("NewsAPI query: %d items for: %s...", len(entries), query[:50])
            all_entries.extend(entries)

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for e in all_entries:
            if e["source_url"] not in seen_urls:
                seen_urls.add(e["source_url"])
                unique.append(e)

        return unique

    def close(self):
        self.client.close()
