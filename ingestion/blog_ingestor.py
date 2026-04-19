import logging
from datetime import datetime, timezone
from typing import Generator
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)

# Blog pages to scrape (fallback when RSS is insufficient)
BLOG_PAGES = {
    # ── Major AI Companies ──
    "Anthropic": "https://www.anthropic.com/research",
    "Google AI": "https://blog.google/technology/ai/",
    "Meta AI": "https://ai.meta.com/blog/",
    "Amazon AI": "https://aws.amazon.com/blogs/machine-learning/",
    "Nvidia": "https://blogs.nvidia.com/blog/category/gpu/",
    "IBM AI": "https://www.ibm.com/blog/artificial-intelligence/",
    "Microsoft AI": "https://www.microsoft.com/en-us/ai/blog/",
    # ── AI Startups ──
    "Mistral": "https://mistral.ai/news",
    "Cohere": "https://cohere.com/blog",
    "xAI": "https://x.ai/blog",
    "Runway": "https://runwayml.com/blog",
    "LangChain": "https://blog.langchain.dev/",
    "Together AI": "https://www.together.ai/blog",
    "Replicate": "https://replicate.com/blog",
    "Weights & Biases": "https://wandb.ai/fully-connected",
    "AnyScale": "https://www.anyscale.com/blog",
    "Writer": "https://writer.com/blog/",
    "Jasper": "https://www.jasper.ai/blog",
    "Glean": "https://www.glean.com/blog",
    # ── AI Healthcare ──
    "DeepMind Health": "https://deepmind.google/blog/",
}

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
    "accelerator", "inference", "training cluster",
    # ── Finance & Business AI ──
    "ai finance", "fintech ai", "trading ai", "ai banking",
    "ai business", "enterprise ai", "ai automation", "ai productivity",
    "ai startup", "ai funding", "ai acquisition",
    # ── Healthcare & Science AI ──
    "ai healthcare", "ai medical", "ai drug", "ai diagnosis",
    "ai biology", "ai protein", "ai pharma", "ai science",
    # ── Development & DevOps AI ──
    "ai coding", "ai developer", "ai devops", "code generation",
    "ai infrastructure", "mlops", "aiops",
    # ── Robotics & Autonomous ──
    "ai robotics", "autonomous", "self-driving",
    # ── Broad catch-all ──
    " ai ", "ai-powered", "ai-driven", "ai-based", "ai-enabled",
]


def _resolve_url(href: str, base_url: str) -> str:
    """Resolve a relative URL against the base domain, not the listing page path.

    BUG-1 FIX: Use urljoin which correctly resolves relative URLs against
    the base URL (domain + path), handling both absolute and relative hrefs.
    """
    if href.startswith(("http://", "https://")):
        return href
    # urljoin handles all relative URL resolution correctly
    return urljoin(base_url, href)


def _extract_date_from_soup(tag) -> str | None:
    """Try to find a real publish date near an article link.

    BUG-3 FIX: Look for <time> tags, datetime attributes, or date-like text
    near the article link instead of always using now().
    """
    # Walk up the DOM to find a parent container with a <time> tag
    parent = tag
    for _ in range(5):  # Check up to 5 levels of parents
        parent = parent.parent
        if parent is None:
            break
        time_tag = parent.find("time")
        if time_tag:
            dt_str = time_tag.get("datetime", "")
            if dt_str:
                try:
                    # Parse ISO format datetime
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return dt.isoformat()
                except (ValueError, TypeError):
                    pass
            # Try the text content of <time>
            text = time_tag.get_text(strip=True)
            if text:
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %b %Y", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                        return dt.isoformat()
                    except ValueError:
                        continue
    return None


def _extract_summary_from_tag(tag) -> str:
    """Extract a real summary from the context around an article link.

    BUG-2 FIX: Instead of copying the title as the summary, look for
    nearby <p> tags, descriptions, or sibling text content.
    """
    parent = tag
    for _ in range(5):
        parent = parent.parent
        if parent is None:
            break
        # Look for <p> tags that might be a description
        p_tags = parent.find_all("p", recursive=True)
        for p in p_tags:
            text = p.get_text(strip=True)
            # Must be substantial text, not just a label
            if len(text) > 40 and text != tag.get_text(strip=True):
                return text[:500]
        # Look for elements with description/excerpt class
        for desc_cls in ["description", "excerpt", "summary", "subtitle", "preview", "blurb"]:
            desc_el = parent.find(class_=lambda c: c and desc_cls in str(c).lower())
            if desc_el:
                text = desc_el.get_text(strip=True)
                if len(text) > 20:
                    return text[:500]
    return ""


class BlogIngestor:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _fetch_page(self, url: str) -> str:
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning("Blog fetch failed for %s: %s", url, e)
            return ""

    def _is_relevant(self, title: str) -> bool:
        text = title.lower()
        return any(kw in text for kw in AI_KEYWORDS)

    def _extract_articles(self, company: str, html: str, base_url: str) -> Generator[dict, None, None]:
        """BUG-4 FIX: Only extract links from article/content containers,
        not navigation/header/footer/sidebar links."""
        if not html:
            return
        soup = BeautifulSoup(html, "html.parser")

        # Remove navigation, header, footer, sidebar elements to reduce noise
        for noise_tag in soup.find_all(["nav", "header", "footer", "aside"]):
            noise_tag.decompose()

        # Also remove elements with common nav/footer class names
        for cls_pattern in ["nav", "menu", "sidebar", "footer", "header", "breadcrumb", "cookie"]:
            for el in soup.find_all(class_=lambda c: c and cls_pattern in str(c).lower()):
                el.decompose()

        # Now look for article links in the cleaned content
        # Prefer links inside <article>, <main>, or content-like containers
        content_container = (
            soup.find("main")
            or soup.find("article")
            or soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["content", "posts", "articles", "blog-list", "feed"]))
            or soup  # fallback to full page if no container found
        )

        for a_tag in content_container.find_all("a", href=True):
            title_text = a_tag.get_text(strip=True)
            if not title_text or len(title_text) < 15:
                continue
            if len(title_text) > 300:
                continue  # Skip mega-long text that's probably not a title
            if not self._is_relevant(title_text):
                continue

            # BUG-1 FIX: Properly resolve relative URLs
            href = _resolve_url(a_tag["href"], base_url)

            # BUG-3 FIX: Try to extract real publish date
            timestamp = _extract_date_from_soup(a_tag)
            if not timestamp:
                timestamp = datetime.now(timezone.utc).isoformat()

            # BUG-2 FIX: Try to extract real summary
            summary = _extract_summary_from_tag(a_tag)
            if not summary:
                summary = title_text  # Only use title as last resort

            yield {
                "title": title_text[:300],
                "company": company,
                "summary": summary[:500],
                "timestamp": timestamp,
                "source_url": href,
                "source_name": "blog",
            }

    def ingest(self) -> list[dict]:
        results = []
        for company, url in BLOG_PAGES.items():
            logger.info("Scraping blog for %s", company)
            html = self._fetch_page(url)
            entries = list(self._extract_articles(company, html, url))
            # Deduplicate by title within same company
            seen_titles = set()
            unique = []
            for e in entries:
                key = (e["title"], e["company"])
                if key not in seen_titles:
                    seen_titles.add(key)
                    unique.append(e)
            logger.info("  → %d relevant articles from %s", len(unique), company)
            results.extend(unique)
        return results

    def close(self):
        self.client.close()
