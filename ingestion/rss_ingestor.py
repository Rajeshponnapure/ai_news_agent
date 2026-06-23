"""
RSS Ingestor — Tier-1 AI sources only.
Focuses on official blogs, release notes, and high-signal tech publications.
No paywalled, low-signal, or opinion-heavy sources.
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Generator

import feedparser
import httpx

from ingestion.feed_config import get_rss_feeds, get_rss_scopes

logger = logging.getLogger(__name__)

# Companies whose launches should ALWAYS be included (never filtered out)
TOP_COMPANIES = {
    "openai", "anthropic", "google", "deepmind", "microsoft", "amazon",
    "aws", "meta", "nvidia", "apple", "github", "mistral", "cohere",
    "perplexity", "xai", "grok", "ollama", "elon musk", "stability", "hugging face", "langchain",
    "gemini", "claude", "chatgpt", "copilot", "bedrock", "sagemaker",
}

# Launch/release signal keywords — these indicate actual new things happening
LAUNCH_KEYWORDS = [
    "launch", "launching", "launched", "launches",
    "release", "released", "releases", "releasing",
    "announce", "announced", "announces", "announcement",
    "introduce", "introduced", "introduces", "introducing",
    "unveil", "unveiled", "unveils", "debut", "debuts",
    "ship", "ships", "shipped", "now available", "available now",
    "new model", "new agent", "new feature", "new product",
    "new version", "v2", "v3", "v4", "v5",
    "update", "upgrade", "rollout", "rolling out", "rolled out",
    "partnership", "acqui", "funding", "raises",  # business events
    "open source", "open-source", "weights released",  # OS releases
    "api", "sdk", "new endpoint", "deprecat",
    # Medical
    "fda approval", "clinical trial", "breakthrough therapy",
    "drug discovery", "diagnosis", "biotech",
    # Robotics
    "humanoid", "boston dynamics", "autonomous vehicle",
    # Safety/Incidents
    "recall", "vulnerability", "incident", "failure", "malfunction",
    "bias", "hallucination", "jailbreak",
]

# Domain filter — these are core AI-relevant domains (word-boundary for short tokens)
DOMAIN_KEYWORDS = [
    # Core AI/ML
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "language model", "foundation model",
    "generative ai", "gen ai", "genai",
    # Products/Models
    "gpt", "claude", "gemini", "llama", "mistral", "grok", "copilot",
    "chatgpt", "bard", "palm", "falcon", "phi", "mixtral",
    "diffusion", "stable diffusion", "dalle", "midjourney", "sora",
    # Tech domains
    "neural network", "transformer", "multimodal", "reasoning",
    "agent", "agentic", "autonomous ai", "ai assistant",
    "benchmark", "evaluation", "alignment", "safety",
    "inference", "training", "fine-tuning", "rlhf",
    # Business/Application
    "ai startup", "ai company", "ai chip", "gpu", "tpu",
    "ai marketing", "ai finance", "ai trading", "fintech ai",
    "ai automation", "ai productivity", "enterprise ai",
    # Medical AI
    "healthcare ai", "medical ai", "ai drug", "clinical ai",
    "ai diagnosis", "ai radiology", "ai biotech", "ai health",
    "ai medicine", "ai surgery", "ai hospital",
    # Robotics
    "robot", "robotics", "humanoid", "drone", "autonomous vehicle",
    "self-driving", "boston dynamics", "spot", "atlas", "ai robot",
    # AI Safety & Incidents
    "ai safety", "ai alignment", "ai bias", "ai hallucination",
    "ai malfunction", "ai incident", "ai regulation", "ai governance",
    "red team", "jailbreak", "ai risk", "ai ethics",
]


def _is_relevant(title: str, summary: str = "", scope: str = "ai") -> bool:
    """Strict relevance check — must be about AI and from a known domain."""
    if scope == "world":
        return True  # world scope feeds accept all recent items
    text = f" {title} {summary} ".lower()
    # Word-boundary match for short tokens like "ai" to avoid
    # hitting "available", "training", "email", "campaign", etc.
    return any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in DOMAIN_KEYWORDS)


def _is_launch_event(title: str, summary: str = "") -> bool:
    """Check if this entry is about an actual launch/release/announcement."""
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in LAUNCH_KEYWORDS)


def _is_top_company(title: str, summary: str = "", feed_name: str = "") -> bool:
    """Check if this is from or about a top AI company."""
    text = f"{title} {summary} {feed_name}".lower()
    return any(co in text for co in TOP_COMPANIES)


class RSSIngestor:
    def __init__(self):
        self.client = httpx.Client(timeout=20.0, follow_redirects=True)
        self.rss_feeds = get_rss_feeds()
        self.rss_scopes = get_rss_scopes()

    def _fetch_feed(self, name: str, url: str) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        try:
            resp = self.client.get(url, headers={"User-Agent": "AI-News-Agent/1.0"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning("RSS fetch failed [%s]: %s", name, e)
            return []

        scope = self.rss_scopes.get(name, "ai")
        entries = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            link = entry.get("link", "")

            if not title or not link:
                continue
            # Strip HTML from summary
            if "<" in summary:
                from bs4 import BeautifulSoup
                summary = BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)
            summary = summary[:500]

            # Parse timestamp
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                try:
                    dt = datetime(*published[:6], tzinfo=timezone.utc)
                    ts = dt.isoformat()
                    # Skip old articles (older than 48 hours) to avoid flooding
                    if datetime.now(timezone.utc) - dt > timedelta(hours=48):
                        continue
                except Exception:
                    ts = "1970-01-01T00:00:00+00:00"
            else:
                ts = "1970-01-01T00:00:00+00:00"

            # Strict relevance: must be AI-related (or world scope)
            if not _is_relevant(title, summary, scope):
                continue

            # Determine if this is a launch event
            is_launch = _is_launch_event(title, summary)
            is_top_co = _is_top_company(title, summary, name)

            entries.append({
                "title": title[:300],
                "company": name,
                "summary": summary,
                "timestamp": ts,
                "source_url": link,
                "source_name": "rss",
                "is_launch": is_launch,
                "is_top_company": is_top_co,
            })

        return entries

    def ingest(self) -> list[dict]:
        all_entries = []
        for name, url in self.rss_feeds.items():
            entries = self._fetch_feed(name, url)
            if entries:
                logger.info("RSS [%s]: %d relevant items", name, len(entries))
            all_entries.extend(entries)
        return all_entries

    def close(self):
        self.client.close()