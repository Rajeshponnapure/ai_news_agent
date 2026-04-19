import logging
from datetime import datetime, timezone
from typing import Generator

import feedparser
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# RSS feeds — verified working sources only
RSS_FEEDS = {
    # ── Major AI Companies ──
    "OpenAI": "https://openai.com/blog/rss.xml",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "Amazon AWS": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Nvidia Blog": "https://nvidianews.nvidia.com/blog/feed",
    # ── Tech News Aggregators (verified working) ──
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "Wired": "https://www.wired.com/feed/rss",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "ZDNet": "https://www.zdnet.com/news/rss.xml",
    "Engadget": "https://www.engadget.com/rss.xml",
    "Gizmodo": "https://gizmodo.com/rss",
    "CNET": "https://www.cnet.com/rss/news/",
    # ── AI Research & Science ──
    "LessWrong": "https://www.lesswrong.com/feed.xml",
    "AI Alignment Forum": "https://www.alignmentforum.org/rss.xml",
    "Towards Data Science": "https://towardsdatascience.com/feed",
    "Papers With Code": "https://paperswithcode.com/rss",
    # ── Business & Finance Tech (verified accessible feeds only) ──
    # NOTE: Bloomberg, Reuters, Financial Times removed — paywalled/block automated access
    "CNBC Technology": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
}

# Broad AI keywords — covers all domains: models, finance, healthcare, dev, chips, robotics, etc.
AI_KEYWORDS = [
    # ── Core AI / ML ──
    "artificial intelligence", "machine learning", "deep learning",
    "model release", "model update", "new model", "launch", "breakthrough",
    "gpt", "claude", "gemini", "llama", "mistral", "diffusion",
    "foundation model", "language model", "large language model", "llm",
    "chatgpt", "copilot", "bedrock", "sagemaker", "transformer",
    "multimodal", "reasoning", "agent", "benchmark", "training",
    "open source", "weights", "checkpoint", "fine-tune", "alignment",
    "safety", "red team", "evaluation", "api", "sdk",
    "neural network", "generative ai", "genai", "gen ai",
    "chatbot", "assistant", "embedding", "rag", "retrieval",
    # ── AI Chips & Hardware ──
    "gpu", "tpu", "npu", "ai chip", "ai hardware", "cuda",
    "nvidia", "h100", "h200", "b200", "blackwell", "hopper",
    "accelerator", "inference", "training cluster", "data center",
    # ── Finance & Business AI ──
    "ai finance", "fintech ai", "trading ai", "ai banking",
    "ai accounting", "ai insurance", "ai compliance", "ai risk",
    "ai business", "enterprise ai", "ai automation", "ai productivity",
    "ai strategy", "ai adoption", "ai roi", "ai investment",
    "ai startup", "ai funding", "ai acquisition", "ai valuation",
    # ── Healthcare & Science AI ──
    "ai healthcare", "ai medical", "ai drug", "ai diagnosis",
    "ai biology", "ai protein", "ai clinical", "ai pharma",
    "ai science", "ai research", "ai discovery",
    # ── Development & DevOps AI ──
    "ai coding", "ai developer", "ai devops", "ai testing",
    "code generation", "ai debugging", "ai deployment",
    "ai infrastructure", "mlops", "aiops",
    # ── Robotics & Autonomous ──
    "ai robotics", "autonomous", "self-driving", "ai vehicle",
    "ai drone", "ai manufacturing", "ai supply chain",
    # ── Regulation & Ethics ──
    "ai regulation", "ai law", "ai ethics", "ai governance",
    "ai policy", "ai act", "ai safety", "ai bias",
    # ── Broad catch-all ──
    " ai ", "ai-powered", "ai-driven", "ai-based", "ai-enabled",
    "artificial intelligence", "machine-learning",
]


class RSSIngestor:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            return feedparser.parse(resp.text)
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", url, e)
            return feedparser.FeedParserDict()

    def _is_relevant(self, title: str, summary: str) -> bool:
        text = f"{title} {summary}".lower()
        return any(kw in text for kw in AI_KEYWORDS)

    def _extract_entries(self, company: str, feed: feedparser.FeedParserDict) -> Generator[dict, None, None]:
        for entry in getattr(feed, "entries", []):
            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "").strip()
            if not title or not self._is_relevant(title, summary):
                continue

            link = getattr(entry, "link", "")
            published = getattr(entry, "published", None)
            if published:
                try:
                    ts = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    ts = datetime.now(timezone.utc).isoformat()
            else:
                ts = datetime.now(timezone.utc).isoformat()

            yield {
                "title": title[:300],
                "company": company,
                "summary": summary[:500],
                "timestamp": ts,
                "source_url": link,
                "source_name": "rss",
            }

    def ingest(self) -> list[dict]:
        results = []
        for company, url in RSS_FEEDS.items():
            logger.info("Ingesting RSS for %s", company)
            feed = self._fetch_feed(url)
            entries = list(self._extract_entries(company, feed))
            logger.info("  → %d relevant entries from %s", len(entries), company)
            results.extend(entries)
        return results

    def close(self):
        self.client.close()
