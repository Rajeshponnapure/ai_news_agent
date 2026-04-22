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
    "OpenAI":           "https://openai.com/blog",
    "Anthropic":        "https://www.anthropic.com/news",
    "Google DeepMind":  "https://deepmind.google/discover/blog/",
    "Google AI":        "https://blog.google/technology/ai/",
    "Meta AI":          "https://ai.meta.com/blog/",
    "xAI":              "https://x.ai/blog",
    "Mistral AI":       "https://mistral.ai/news",
    "Cohere":           "https://cohere.com/blog",
    "Perplexity":       "https://blog.perplexity.ai",
    # Big Tech AI
    "Microsoft AI":     "https://www.microsoft.com/en-us/ai/blog/",
    "GitHub":           "https://github.blog/",
    "Amazon AWS AI":    "https://aws.amazon.com/blogs/machine-learning/",
    "Nvidia":           "https://blogs.nvidia.com/blog/category/generative-ai/",
    "Apple ML":         "https://machinelearning.apple.com/",
    # AI Platforms
    "Hugging Face":     "https://huggingface.co/blog",
    "LangChain":        "https://blog.langchain.dev/",
    "Ollama":           "https://ollama.com/blog",
    "vLLM":             "https://blog.vllm.ai/",
    # Finance AI (user's domain)
    "Palantir":         "https://palantir.com/newsroom/blog/",
    "Databricks":       "https://www.databricks.com/blog",
    # Marketing AI (user's domain)
    "HubSpot AI":       "https://blog.hubspot.com/marketing/ai-marketing",
    "Salesforce AI":    "https://www.salesforce.com/blog/tag/artificial-intelligence/",
    "Adobe AI":         "https://blog.adobe.com/en/topics/ai",
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
        # Must have at least AI AND (launch OR minimum length for company blogs)
        return has_ai and (has_launch or len(t) > 20)

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
                if datetime.now(timezone.utc) - dt > timedelta(hours=24):
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
