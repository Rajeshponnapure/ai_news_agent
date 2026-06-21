"""
RSS Ingestor — Tier-1 AI sources only.
Focuses on official blogs, release notes, and high-signal tech publications.
No paywalled, low-signal, or opinion-heavy sources.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Generator

import feedparser
import httpx

logger = logging.getLogger(__name__)

# ── Tier-1 RSS Feeds ───────────────────────────────────────────────────────
# Only high-signal sources that publish actual launches, releases, and
# product announcements. No opinion sites, no paywalls.
RSS_FEEDS = {
    # ── Official AI Company Blogs ──
    "OpenAI Blog":          "https://openai.com/news/rss.xml",
    # Anthropic: No working public RSS feed - using blog scraper instead
    "Google AI Blog":       "https://blog.google/technology/ai/rss/",
    "Google DeepMind":      "https://deepmind.google/blog/rss.xml",
    "Microsoft AI Blog":    "https://news.microsoft.com/source/topics/ai/feed/",  # old blogs.microsoft.com/ai/feed/ → 410 Gone
    "AWS Machine Learning": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Nvidia Blog":          "https://blogs.nvidia.com/feed/",
    "GitHub Blog":          "https://github.blog/feed/",
    "Hugging Face Blog":    "https://huggingface.co/blog/feed.xml",
    "LangChain Blog":       "https://www.langchain.com/blog/rss.xml",
    "Cohere Blog":          "https://cohere.com/blog/rss.xml",
    "Amazon Science":      "https://www.amazon.science/index.rss",
    # Note: Meta AI, Mistral, Stability AI, xAI, Perplexity don't have working public RSS feeds

    # ── Tier-1 Tech News (AI-specific) ──
    "TechCrunch AI":        "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI":       "https://venturebeat.com/category/ai/feed/",
    "Ars Technica AI":      "https://arstechnica.com/tag/ai/feed/",
    "MIT Tech Review AI":   "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "ZDNet AI":             "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",

    # ── Additional High-Signal AI News ──
    "AI Business":          "https://aibusiness.com/rss.xml",
    "Unite.AI":             "https://www.unite.ai/feed/",
    "Analytics India Mag":  "https://analyticsindiamag.com/feed/",
    "The Verge AI":         "https://www.theverge.com/rss/index.xml",
    "Wired AI":             "https://www.wired.com/feed/tag/ai/latest/rss",
    "CNET AI":              "https://www.cnet.com/rss/news/",
    # Note: AI Trends RSS times out frequently - disabled
    # "AI Trends":            "https://www.aitrends.com/feed/",
    "MarkTechPost AI":      "https://www.marktechpost.com/category/artificial-intelligence/feed/",

    # ── AI in Finance & Marketing ──
    "CNBC Technology":      "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "Forbes Tech":          "https://www.forbes.com/technology/feed/",
    "Marketing AI Inst.":   "https://www.marketingaiinstitute.com/blog/rss.xml",
    "Product Hunt AI":      "https://www.producthunt.com/feed",

    # ── Research & Papers (limited to avoid flooding) ──
    "Papers With Code":     "https://paperswithcode.com/rss",
    # Note: arXiv feeds temporarily disabled - too many papers flood alerts
    # "arXiv AI":             "http://export.arxiv.org/rss/cs.AI",
    # "arXiv ML":             "http://export.arxiv.org/rss/cs.LG",

    # ═══════════════════════════════════════════════════════════════════════
    # 🏥 MEDICAL & HEALTHCARE AI
    # ═══════════════════════════════════════════════════════════════════════
    "STAT Health AI":       "https://www.statnews.com/tag/artificial-intelligence/feed/",
    "Nature Machine Intelligence": "https://www.nature.com/natmachintell.rss",
    "Science Daily AI":     "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
    # NIH press pages (nih.gov) hard-block bots (403) — surfaced via Google News RSS instead.
    "NIH Research News":    "https://news.google.com/rss/search?q=NIH+artificial+intelligence+health+when:7d&hl=en-US&gl=US&ceid=US:en",

    # ═══════════════════════════════════════════════════════════════════════
    # 🎓 ACADEMIC AI NEWS
    # news.mit.edu hard-blocks bots (403) regardless of UA/headers — via Google News RSS.
    # ═══════════════════════════════════════════════════════════════════════
    "MIT News AI":          "https://news.google.com/rss/search?q=MIT+artificial+intelligence+when:7d&hl=en-US&gl=US&ceid=US:en",
    "MIT News ML":          "https://news.google.com/rss/search?q=MIT+machine+learning+when:7d&hl=en-US&gl=US&ceid=US:en",

    # ═══════════════════════════════════════════════════════════════════════
    # 🤖 ROBOTICS
    # ═══════════════════════════════════════════════════════════════════════
    "IEEE Spectrum":           "https://spectrum.ieee.org/feed/rss/",
    "Robotics Business Review": "https://www.roboticsbusinessreview.com/feed/",
    "The Robot Report":        "https://www.therobotreport.com/feed/",
    "Robotics 24/7":           "https://www.robotics247.com/rss/",
    "TechCrunch Robotics":     "https://techcrunch.com/category/robotics/feed/",
    "Google Research Blog":    "https://research.google/blog/rss/",

    # ═══════════════════════════════════════════════════════════════════════
    # ⚠️  AI SAFETY, MISUSE & MALFUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════
    "AI Incident Database":   "https://incidentdatabase.ai/rss.xml",
    "Future of Life AI":      "https://futureoflife.org/category/ai/feed/",

    # ═══════════════════════════════════════════════════════════════════════
    # 🌍 GENERAL TECH & GLOBAL AI NEWS
    # ═══════════════════════════════════════════════════════════════════════
    "BBC Tech":               "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "The Guardian Tech":      "https://www.theguardian.com/technology/rss",
    "NYT AI":                 "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/topic/subject/artificial-intelligence/rss.xml",
    "WSJ AI":                 "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "Vox":                    "https://www.vox.com/rss/index.xml",
    "Engadget":               "https://www.engadget.com/rss.xml",
    "Bloomberg Tech":         "https://feeds.bloomberg.com/technology/news.rss",
}

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
                    dt = datetime(*published[:6], tzinfo=timezone.utc)
                    ts = dt.isoformat()
                    # Skip old articles (older than 48 hours) to avoid flooding
                    if datetime.now(timezone.utc) - dt > timedelta(hours=48):
                        continue
                except Exception:
                    ts = "1970-01-01T00:00:00+00:00"
            else:
                ts = "1970-01-01T00:00:00+00:00"

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
