"""
RSS Ingestor — Tier-1 AI sources only.
Focuses on official blogs, release notes, and high-signal tech publications.
No paywalled, low-signal, or opinion-heavy sources.
"""
import logging
from datetime import datetime, timezone
from typing import Generator

import feedparser
import httpx

logger = logging.getLogger(__name__)

# ── Tier-1 RSS Feeds ───────────────────────────────────────────────────────
# Only high-signal sources that publish actual launches, releases, and
# product announcements. No opinion sites, no paywalls.
RSS_FEEDS = {
    # ── Official AI Company Blogs ──
    "OpenAI Blog":          "https://openai.com/blog/rss.xml",
    "Anthropic News":       "https://www.anthropic.com/rss.xml",
    "Google AI Blog":       "https://blog.google/technology/ai/rss/",
    "Google DeepMind":      "https://deepmind.google/blog/rss.xml",
    "Meta AI Blog":         "https://ai.meta.com/blog/rss/",
    "Microsoft AI Blog":    "https://blogs.microsoft.com/ai/feed/",
    "AWS Machine Learning": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Nvidia Blog":          "https://blogs.nvidia.com/feed/",
    "GitHub Blog":          "https://github.blog/feed/",
    "Mistral AI":           "https://mistral.ai/news/rss",
    "Hugging Face Blog":    "https://huggingface.co/blog/feed.xml",
    "LangChain Blog":       "https://blog.langchain.dev/rss/",
    "Perplexity Blog":      "https://blog.perplexity.ai/rss",
    "Cohere Blog":          "https://cohere.com/blog/rss",
    "Stability AI":         "https://stability.ai/news/rss.xml",
    "xAI Blog":             "https://x.ai/blog/rss.xml",

    # ── Tier-1 Tech News (AI-specific) ──
    "TechCrunch AI":        "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "VentureBeat AI":       "https://venturebeat.com/category/ai/feed/",
    "The Verge AI":         "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "Wired AI":             "https://www.wired.com/tag/artificial-intelligence/rss",
    "Ars Technica AI":      "https://arstechnica.com/tag/ai/feed/",
    "MIT Tech Review AI":   "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "ZDNet AI":             "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",

    # ── AI in Finance & Marketing (user's work domain) ──
    "CNBC Technology":      "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "Forbes Tech":          "https://www.forbes.com/technology/feed/",
    "Marketing AI Inst.":   "https://www.marketingaiinstitute.com/blog/rss.xml",

    # ── Research & Papers ──
    "Papers With Code":     "https://paperswithcode.com/rss",
    "AI Alignment Forum":   "https://www.alignmentforum.org/rss.xml",
}

# Companies whose launches should ALWAYS be included (never filtered out)
TOP_COMPANIES = {
    "openai", "anthropic", "google", "deepmind", "microsoft", "amazon",
    "aws", "meta", "nvidia", "apple", "github", "mistral", "cohere",
    "perplexity", "xai", "grok", "stability", "hugging face", "langchain",
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
]

# Domain filter — these are core AI-relevant domains
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
]


def _is_relevant(title: str, summary: str = "") -> bool:
    """Strict relevance check — must be about AI and from a known domain."""
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in DOMAIN_KEYWORDS)


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

    def _fetch_feed(self, name: str, url: str) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        try:
            resp = self.client.get(url, headers={"User-Agent": "AI-News-Agent/1.0"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning("RSS fetch failed [%s]: %s", name, e)
            return []

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
                    ts = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    ts = datetime.now(timezone.utc).isoformat()
            else:
                ts = datetime.now(timezone.utc).isoformat()

            # Strict relevance: must be AI-related
            if not _is_relevant(title, summary):
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
        for name, url in RSS_FEEDS.items():
            entries = self._fetch_feed(name, url)
            if entries:
                logger.info("RSS [%s]: %d relevant items", name, len(entries))
            all_entries.extend(entries)
        return all_entries

    def close(self):
        self.client.close()
