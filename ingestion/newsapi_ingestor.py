import logging
from datetime import datetime, timezone, timedelta

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# NewsAPI.org — searches 50,000+ news sources worldwide
NEWS_API_URL = "https://newsapi.org/v2/everything"

# Search queries to cover all AI domains
SEARCH_QUERIES = [
    "artificial intelligence",
    "AI model release OR AI launch",
    "ChatGPT OR GPT OR Claude OR Gemini OR Llama",
    "AI startup funding OR AI acquisition",
    "AI chip OR GPU OR Nvidia OR TPU",
    "AI healthcare OR AI drug discovery",
    "AI finance OR fintech AI OR AI banking",
    "AI robotics OR autonomous vehicle",
    "AI regulation OR AI policy OR AI ethics",
    "generative AI OR LLM OR foundation model",
    "Mistral OR DeepSeek OR xAI OR Perplexity",
    "AI coding OR AI developer OR AI devops",
]


class NewsAPIIngestor:
    """Fetches AI news from NewsAPI.org — covers 50,000+ sources worldwide."""

    def __init__(self):
        self.api_key = settings.NEWS_API_KEY
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _fetch_articles(self, query: str) -> list[dict]:
        if not self.api_key:
            logger.warning("NEWS_API_KEY not set, skipping NewsAPI")
            return []

        # Last 24 hours
        from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        params = {
            "q": query,
            "from": from_date,
            "to": to_date,
            "sortBy": "relevancy",
            "pageSize": 20,
            "language": "en",
            "apiKey": self.api_key,
        }
        try:
            resp = self.client.get(NEWS_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "ok":
                logger.warning("NewsAPI returned status: %s", data.get("status"))
                return []
            return data.get("articles", [])
        except Exception as e:
            logger.warning("NewsAPI fetch failed for query '%s': %s", query, e)
            return []

    def _extract_company(self, article: dict) -> str:
        """Try to infer the company from the source name or title."""
        source_name = article.get("source", {}).get("name", "")
        title = article.get("title", "")
        text = f"{source_name} {title}".lower()

        company_map = {
            "openai": "OpenAI", "chatgpt": "OpenAI", "gpt": "OpenAI",
            "anthropic": "Anthropic", "claude": "Anthropic",
            "google": "Google", "gemini": "Google", "deepmind": "Google DeepMind",
            "microsoft": "Microsoft", "copilot": "Microsoft",
            "meta": "Meta", "llama": "Meta",
            "amazon": "Amazon", "aws": "Amazon",
            "nvidia": "Nvidia",
            "mistral": "Mistral",
            "hugging": "Hugging Face",
            "stability": "Stability AI",
            "cohere": "Cohere",
            "perplexity": "Perplexity",
            "xai": "xAI", "grok": "xAI",
            "deepseek": "DeepSeek",
            "intel": "Intel",
            "ibm": "IBM",
            "oracle": "Oracle",
        }
        for key, company in company_map.items():
            if key in text:
                return company
        return source_name or "NewsAPI"

    def ingest(self) -> list[dict]:
        if not self.api_key:
            logger.info("NewsAPI skipped (no API key)")
            return []

        results = []
        seen_titles = set()

        for query in SEARCH_QUERIES:
            logger.info("NewsAPI query: %s", query)
            articles = self._fetch_articles(query)
            for article in articles:
                title = article.get("title", "").strip()
                if not title or title == "[Removed]":
                    continue
                # Dedup within NewsAPI results
                title_key = title.lower().strip()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                published = article.get("publishedAt", "")
                url = article.get("url", "")
                description = article.get("description", "") or ""
                company = self._extract_company(article)

                results.append({
                    "title": title[:300],
                    "company": company,
                    "summary": description[:500],
                    "timestamp": published or datetime.now(timezone.utc).isoformat(),
                    "source_url": url,
                    "source_name": "newsapi",
                })

        logger.info("NewsAPI returned %d unique articles", len(results))
        return results

    def close(self):
        self.client.close()
