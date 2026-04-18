import logging
from datetime import datetime, timezone
from typing import Generator

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
    "Perplexity": "https://www.perplexity.ai/",
    "Runway": "https://runwayml.com/blog",
    "Reka AI": "https://reka.ai/",
    "Adept AI": "https://www.adept.ai/",
    "Inflection AI": "https://inflection.ai/",
    "Character.AI": "https://character.ai/",
    "Sakana AI": "https://sakana.ai/",
    "Imbue": "https://www.imbue.com/",
    "Liquid AI": "https://www.liquid.ai/",
    "Glean": "https://www.glean.com/blog",
    "Jasper": "https://www.jasper.ai/blog",
    "Writer": "https://writer.com/blog/",
    "AnyScale": "https://www.anyscale.com/blog",
    "Together AI": "https://www.together.ai/blog",
    "Replicate": "https://replicate.com/blog",
    "LangChain": "https://blog.langchain.dev/",
    "Weights & Biases": "https://wandb.ai/fully-connected",
    # ── AI Finance & Business ──
    "Bloomberg AI": "https://www.bloomberg.com/topics/artificial-intelligence",
    "JPMorgan AI": "https://www.jpmorgan.com/technology/artificial-intelligence",
    # ── AI Healthcare ──
    "DeepMind Health": "https://deepmind.google/blog/",
    "Recursion Pharma": "https://www.recursion.com/blog",
    "Insitro": "https://insitro.com/",
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

    def _extract_articles(self, company: str, html: str) -> Generator[dict, None, None]:
        if not html:
            return
        soup = BeautifulSoup(html, "html.parser")

        # Try common article link patterns
        for a_tag in soup.find_all("a", href=True):
            title_text = a_tag.get_text(strip=True)
            if not title_text or len(title_text) < 10:
                continue
            if not self._is_relevant(title_text):
                continue

            href = a_tag["href"]
            if href.startswith("/"):
                # Resolve relative URL
                base = BLOG_PAGES.get(company, "")
                if base:
                    href = base.rstrip("/") + href

            yield {
                "title": title_text[:300],
                "company": company,
                "summary": title_text[:500],  # Blog scraping gives limited summary
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_url": href,
                "source_name": "blog",
            }

    def ingest(self) -> list[dict]:
        results = []
        for company, url in BLOG_PAGES.items():
            logger.info("Scraping blog for %s", company)
            html = self._fetch_page(url)
            entries = list(self._extract_articles(company, html))
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
