"""
Blog Ingestor — Major AI company blogs only.
Prioritizes official company pages for launch and release announcements.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Generator
from urllib.parse import urljoin
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Official company blogs — ONLY major AI companies ───────────────────────
BLOG_PAGES = {
    # Core AI Labs
    # OpenAI: Blocks bot scraping (403) - using RSS feed instead
    "Anthropic":        "https://www.anthropic.com/news",
    "Google DeepMind":  "https://deepmind.google/blog/",
    "Google AI":        "https://blog.google/technology/ai/",
    "Meta AI":          "https://ai.meta.com/blog/",
    "Mistral AI":       "https://mistral.ai/news",
    "Cohere":           "https://cohere.com/blog",
    "OpenAI Dev Blog":    "https://developers.openai.com/blog",
    # OpenAI's main news page blocks bot scraping; covered via RSS/NewsAPI/GitHub instead.

    # Big Tech AI
    "Microsoft AI":     "https://www.microsoft.com/en-us/ai/blog/",
    "Microsoft Security AI": "https://www.microsoft.com/en-us/security/blog/topic/ai-and-machine-learning/",
    "Microsoft Cloud Blog":  "https://www.microsoft.com/en-us/microsoft-cloud/blog/",
    "GitHub":           "https://github.blog/",
    "Amazon AWS AI":    "https://aws.amazon.com/blogs/machine-learning/",
    "AWS Cloud Ops AI": "https://aws.amazon.com/blogs/mt/tag/ai-ml/",
    "AWS News AI":      "https://aws.amazon.com/blogs/aws/category/artificial-intelligence/",
    "Nvidia":           "https://blogs.nvidia.com/",
    "NVIDIA Newsroom":  "https://nvidianews.nvidia.com/news/latest",
    "Google Cloud AI":  "https://cloud.google.com/blog/products/ai-machine-learning",
    "Apple ML":         "https://machinelearning.apple.com/",
    "Amazon Science":   "https://www.amazon.science/",

    # AI Platforms
    "Hugging Face":     "https://huggingface.co/blog",
    "LangChain":        "https://blog.langchain.dev/",
    "Ollama":           "https://ollama.com/blog",
    "vLLM":             "https://vllm.ai/blog/",
    "LlamaIndex":      "https://www.llamaindex.ai/blog/",
    # Perplexity and xAI currently return 403 for this scraper UA; covered via other ingestors.
    "Stability AI":    "https://stability.ai/news-updates",
    "Meta AI Research": "https://ai.meta.com/research/",

    # Finance AI
    "Databricks":       "https://www.databricks.com/blog",
    "Snowflake AI":    "https://www.snowflake.com/en/blog/",

    # Marketing AI
    "HubSpot AI":       "https://blog.hubspot.com/marketing/ai-marketing",
    "Salesforce AI":    "https://www.salesforce.com/blog/tag/artificial-intelligence/",
    "Adobe AI":        "https://blog.adobe.com/en/topics/artificial-intelligence",

    # ═══════════════════════════════════════════════════════════════════════
    # 🏥 MEDICAL & HEALTHCARE AI
    # ═══════════════════════════════════════════════════════════════════════
    "Google Health AI":  "https://health.google/",
    # NIH Research News moved to RSS_FEEDS (Google News) — www.nih.gov returns 403 to scrapers.
    "WEF AI":           "https://www.weforum.org/topics/artificial-intelligence/",
    "Stanford AIMI":    "https://aimi.stanford.edu/news",
    "Nature AI":        "https://www.nature.com/natmachintell/",
    # Note: Nature Machine Intelligence articles listed in RESEARCH section below

    # ═══════════════════════════════════════════════════════════════════════
    # 🤖 ROBOTICS
    # ═══════════════════════════════════════════════════════════════════════
    "Boston Dynamics":  "https://www.bostondynamics.com/blog",
    "NVIDIA Robotics":  "https://developer.nvidia.com/blog/tag/robotics/",
    "Google AI Blog":   "https://ai.googleblog.com/",
    "IEEE Spectrum Robotics": "https://spectrum.ieee.org/topic/robotics/",
    "Robotics 24/7":    "https://www.robotics247.com/",
    "TechCrunch Robotics": "https://techcrunch.com/category/robotics/",

    # ═══════════════════════════════════════════════════════════════════════
    # ⚠️  AI SAFETY, MISUSE & MALFUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════
    "AI Safety Institute": "https://www.aisi.gov.uk/",
    "Center for AI Safety": "https://www.safe.ai/blog",
    "AI Incident Database": "https://incidentdatabase.ai/blog/",
    "Future of Life Institute": "https://futureoflife.org/category/ai/",

    # ═══════════════════════════════════════════════════════════════════════
    # 🌍 GENERAL TECH & AI NEWS
    # ═══════════════════════════════════════════════════════════════════════
    "Wired AI":         "https://www.wired.com/tag/artificial-intelligence/",
    "The Verge AI":     "https://www.theverge.com/ai-artificial-intelligence",
    "NYT AI":           "https://www.nytimes.com/topic/subject/artificial-intelligence",
    "BBC Tech":         "https://www.bbc.co.uk/news/technology",
    "Vox Tech":         "https://www.vox.com/technology",
    # VentureBeat AI covered by working RSS feed (RSS_FEEDS) — HTML scrape duplicated it and hit 429.
    "InformationWeek":  "https://www.informationweek.com/machine-learning-ai",
    # MIT News AI / ML moved to RSS_FEEDS (Google News) — news.mit.edu returns 403 to scrapers.
    "ScienceDaily AI":  "https://www.sciencedaily.com/news/computers_math/artificial_intelligence/",
    "TechCrunch GenAI": "https://techcrunch.com/tag/generative-ai/",

    # ═══════════════════════════════════════════════════════════════════════
    # 🔬 AI RESEARCH & SCIENCE (beyond core companies)
    # ═══════════════════════════════════════════════════════════════════════
    "DeepMind Research": "https://deepmind.google/research/",
    # Apple ML Research is the same URL as Apple ML - covered above
    "Meta Research":     "https://research.facebook.com/publications/",
    "Google Research":   "https://research.google/blog/",
    "Nature Machine Intelligence": "https://www.nature.com/natmachintell/articles",
}

# High-signal launch/event keywords — must appear for the article to matter
LAUNCH_KEYWORDS = [
    "launch", "launches", "launched", "launching",
    "release", "releases", "released", "releasing",
    "announce", "announces", "announced", "announcement",
    "introduce", "introduces", "introduced", "introducing",
    "unveil", "unveils", "unveiled",
    "debut", "debuts",
    "available", "now available", "generally available", "ga",
    "new model", "new agent", "new version", "new feature",
    "update", "upgrade", "v2", "v3", "v4", "v5",
    "open source", "open-source", "weights",
    "partnership", "acqui", "series", "funding", "raises",
    "api", "sdk",
]

# Any of these must be in the title for it to be relevant
AI_MUST_HAVE = [
    "ai", "artificial intelligence", "machine learning",
    "model", "agent", "llm", "gpt", "claude", "gemini", "llama",
    "copilot", "chatgpt", "neural", "generative", "automation",
    "bedrock", "sagemaker", "deepmind", "openai", "anthropic",
    # Medical AI
    "medical", "healthcare", "health", "clinical", "diagnosis", "drug",
    "biotech", "radiology", "pathology", "surgical", "therapeutic",
    "genomics", "proteomics", "pharma", "patient", "hospital",
    # Robotics
    "robot", "robotics", "drone", "autonomous", "humanoid", "quadruped",
    "manipulator", "actuator", "sensor fusion", "slam", "navigation",
    "boston dynamics", "spot", "atlas", "optim us", "telsa bot",
    "automation", "industrial robot", "cobot", "collaborative robot",
    # AI Safety & Misuse
    "safety", "alignment", "misuse", "malfunction", "bias", "hallucination",
    "red team", "jailbreak", "adversarial", "robustness", "guardrail",
    "regulation", "governance", "oversight", "policy", "ethics",
    "responsible", "transparency", "explainability", "audit",
    # General tech
    "tech", "technology", "startup", "funding", "innovation",
    "breakthrough", "discovery", "research", "science", "engineering",
    "chip", "gpu", "tpu", "processor", "semiconductor",
    "cuda", "tensor", "inference", "training", "compute",
]


def _resolve_url(href: str, base_url: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base_url, href)


def _extract_date(tag) -> str | None:
    # Attempt to extract text dates (e.g. "August 24, 2023")
    text = tag.get_text(strip=True)
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', text, re.IGNORECASE)
    if m:
        dt_str = m.group(0)
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

    parent = tag
    for _ in range(6):
        parent = getattr(parent, "parent", None)
        if parent is None:
            break
        time_tag = parent.find("time")
        if time_tag:
            dt_str = time_tag.get("datetime", "")
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return dt.isoformat()
                except Exception:
                    pass
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %b %Y"):
                try:
                    dt = datetime.strptime(time_tag.get_text(strip=True), fmt)
                    return dt.replace(tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass
    return None


def _extract_summary(tag) -> str:
    parent = tag
    for _ in range(5):
        parent = getattr(parent, "parent", None)
        if parent is None:
            break
        for p in parent.find_all("p", recursive=True):
            text = p.get_text(strip=True)
            if len(text) > 40 and text.lower() != tag.get_text(strip=True).lower():
                return text[:500]
        for cls in ["description", "excerpt", "summary", "subtitle", "preview"]:
            el = parent.find(class_=lambda c: c and cls in str(c).lower())
            if el:
                text = el.get_text(strip=True)
                if len(text) > 20:
                    return text[:500]
    return ""


class BlogIngestor:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _fetch(self, url: str) -> str:
        try:
            r = self.client.get(url, headers={"User-Agent": "AI-News-Agent/1.0"})
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.warning("Blog fetch failed [%s]: %s", url, e)
            return ""

    def _is_relevant(self, title: str) -> bool:
        t = title.lower()
        has_ai = any(k in t for k in AI_MUST_HAVE)
        has_launch = any(k in t for k in LAUNCH_KEYWORDS)
        # Must have at least AI keywords - launch keywords optional but preferred
        # Relaxed filter to catch more relevant posts
        return has_ai

    def _extract_articles(self, company: str, html: str, base_url: str) -> list[dict]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")

        # Strip navigation/footer noise
        for tag in soup.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        for cls in ["nav", "menu", "sidebar", "footer", "breadcrumb", "cookie", "banner"]:
            for el in soup.find_all(class_=lambda c: c and cls in str(c).lower()):
                el.decompose()

        # Target content containers
        container = (
            soup.find("main")
            or soup.find(class_=lambda c: c and any(
                k in str(c).lower() for k in ["content", "posts", "articles", "blog", "feed"]
            ))
            or soup
        )

        results = []
        seen = set()

        for a in container.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 15 or len(title) > 250:
                continue
            if not self._is_relevant(title):
                continue
            if title in seen:
                continue
            seen.add(title)

            href = _resolve_url(a["href"], base_url)
            ts = _extract_date(a) or "1970-01-01T00:00:00+00:00"
            
            # Skip old articles (older than 48 hours)
            try:
                dt = datetime.fromisoformat(ts)
                if datetime.now(timezone.utc) - dt > timedelta(hours=48):
                    continue
            except Exception:
                pass

            summary = _extract_summary(a)

            is_launch = any(k in title.lower() for k in LAUNCH_KEYWORDS)

            results.append({
                "title": title[:250],
                "company": company,
                "summary": summary or title,
                "timestamp": ts,
                "source_url": href,
                "source_name": "blog",
                "is_launch": is_launch,
                "is_top_company": True,  # all blog sources are top companies
            })

        return results

    def ingest(self) -> list[dict]:
        all_entries = []
        for company, url in BLOG_PAGES.items():
            logger.info("Scraping blog: %s", company)
            html = self._fetch(url)
            entries = self._extract_articles(company, html, url)
            logger.info("  → %d relevant items from %s", len(entries), company)
            all_entries.extend(entries)
        return all_entries

    def close(self):
        self.client.close()
