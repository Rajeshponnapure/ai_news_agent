"""
Processing Pipeline — strict relevance filtering for AI launch events.
Only keeps content from top AI companies about actual new things happening.
"""
import logging
import re
from datetime import datetime, timezone

from database.db import get_db

logger = logging.getLogger(__name__)

# Companies that always get HIGH priority
TOP_COMPANIES = {
    "openai", "anthropic", "google", "deepmind", "google deepmind",
    "microsoft", "amazon", "aws", "meta", "nvidia", "apple", "github",
    "mistral", "cohere", "perplexity", "xai", "grok", "elon musk", "stability",
    "hugging face", "langchain", "gemini", "google gemini",
}

# HIGH impact: actual model/product launches from major players
HIGH_IMPACT_KEYWORDS = [
    # Major launches
    "gpt-5", "gpt-4o", "gpt4o", "o3", "o4", "claude 4", "claude 3.5",
    "claude opus", "claude sonnet", "claude haiku",
    "gemini 2", "gemini ultra", "gemini flash", "gemini pro",
    "llama 4", "llama3", "llama 3", "llama4",
    "mistral large", "mistral small", "codestral",
    "new model", "model release", "model launch",
    "new agent", "ai agent launch",
    # Product releases
    "launch", "released", "now available", "generally available",
    "open source", "weights released", "open-sourced",
    # Hardware
    "h100", "h200", "b200", "gb200", "blackwell", "new gpu", "new tpu",
    "new chip", "accelerator",
    # Business
    "acquisition", "acqui", "merger", "ipo", "series c", "series d",
    "billion", "funding round",
    # Domain-specific
    "breakthrough", "state of the art", "sota", "frontier model",
    "multimodal", "reasoning model",
]

# MEDIUM impact: updates, features, research
MEDIUM_IMPACT_KEYWORDS = [
    "update", "upgrade", "new feature", "integration",
    "api", "sdk", "new endpoint",
    "partnership", "collaboration", "announcement",
    "series a", "series b", "investment",
    "research paper", "arxiv", "benchmark",
    "open source", "checkpoint",
    "fine-tune", "rlhf", "alignment",
    "ai marketing", "marketing ai", "ad creative",
    "ai finance", "fintech ai", "trading ai", "ai banking",
    "agent", "autonomous", "agentic",
    "code generation", "ai coding", "copilot",
    "multimodal", "vision", "audio", "voice",
    "inference", "performance improvement",
]

# These always get filtered OUT — noise/opinion content
EXCLUDE_KEYWORDS = [
    "opinion", "editorial", "weekly roundup", "newsletter",
    "5 things to know", "what you need to know", "week in review",
    "podcast", "interview question", "job posting", "hiring", "career",
    "stock price", "earnings call", "dividend", "quarterly results",
    "how to use", "tutorial", "guide for beginners",
    "politics", "election", "campaign", "senator", "congress",
    "celebrity", "gossip", "sports",
    "climate change", "covid", "vaccine",  # unrelated news
]

# Categories user cares about
CATEGORIES = {
    "🚀 AI LAUNCHES & RELEASES": [
        "launch", "release", "announce", "introduce", "unveil", "debut",
        "new model", "new agent", "now available", "generally available",
        "open source", "weights", "update", "upgrade",
    ],
    "💰 FINANCE & FINTECH AI": [
        "finance", "fintech", "banking", "trading", "investment", "stock",
        "market", "hedge fund", "wall street", "bloomberg", "palantir",
        "jpmorgan", "goldman", "economy", "financial",
    ],
    "📣 MARKETING & GROWTH AI": [
        "marketing", "advertising", "ad", "campaign", "content generation",
        "social media ai", "creative ai", "brand", "seo ai", "copywriting",
        "hubspot", "salesforce", "adobe", "jasper", "copy.ai",
    ],
    "💻 AI CODING & DEVELOPER TOOLS": [
        "coding", "developer", "github copilot", "code generation",
        "ide", "devops", "sdk", "api", "framework", "open source",
        "cursor", "replit", "tabnine", "codewhisperer",
    ],
    "⚡ HARDWARE & INFRASTRUCTURE": [
        "gpu", "tpu", "chip", "hardware", "nvidia", "h100", "h200",
        "data center", "compute", "cuda", "accelerator", "inference",
        "server", "cloud", "aws", "azure", "google cloud",
    ],
    "🔬 RESEARCH & SCIENCE": [
        "research", "paper", "arxiv", "study", "benchmark", "evaluation",
        "safety", "alignment", "breakthrough", "sota", "frontier",
        "academic", "lab", "university",
    ],
}

CATEGORY_ORDER = [
    "🚀 AI LAUNCHES & RELEASES",
    "💰 FINANCE & FINTECH AI",
    "📣 MARKETING & GROWTH AI",
    "💻 AI CODING & DEVELOPER TOOLS",
    "⚡ HARDWARE & INFRASTRUCTURE",
    "🔬 RESEARCH & SCIENCE",
    "📰 OTHER AI NEWS",
]


def assign_category(title: str, summary: str, company: str = "") -> str:
    """Assign content category to an entry."""
    text = f"{title} {summary} {company}".lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if not scores:
        return "📰 OTHER AI NEWS"
    return max(scores, key=scores.get)


class ProcessingPipeline:
    """Strict pipeline: filters to AI launch events from top companies only."""

    def assign_impact(self, title: str, summary: str, is_launch: bool = False,
                      is_top_company: bool = False) -> str:
        text = f"{title} {summary}".lower()

        # Check exclusions first
        for kw in EXCLUDE_KEYWORDS:
            if kw in text:
                return "low"

        # Top company launch = always HIGH
        if is_top_company and is_launch:
            return "high"

        # High impact keywords
        for kw in HIGH_IMPACT_KEYWORDS:
            if kw in text:
                return "high"

        # Check if from known top company
        company_in_text = any(co in text for co in TOP_COMPANIES)
        if company_in_text and is_launch:
            return "high"

        # Medium impact keywords
        for kw in MEDIUM_IMPACT_KEYWORDS:
            if kw in text:
                return "medium"

        return "low"

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def deduplicate(self, entries: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for entry in entries:
            key = (
                self._normalize(entry["title"]),
                entry["company"].lower().strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(entry)
        return unique

    def filter_noise(self, entries: list[dict]) -> list[dict]:
        """Remove noise. Keep everything that's medium or high impact."""
        filtered = []
        for entry in entries:
            text = f"{entry['title']} {entry.get('summary', '')}".lower()
            # Hard exclude
            if any(kw in text for kw in EXCLUDE_KEYWORDS):
                logger.debug("Excluded: %s", entry["title"][:60])
                continue
            # Keep if medium+ or from top company or is a launch
            if (entry.get("impact_level") in ("high", "medium")
                    or entry.get("is_top_company")
                    or entry.get("is_launch")):
                filtered.append(entry)
        return filtered

    def ingest_and_store(self, raw_entries: list[dict]) -> int:
        """Process raw entries from ingestors and store in DB. Returns count of new entries."""
        db = get_db()
        count = 0

        deduped = self.deduplicate(raw_entries)

        for entry in deduped:
            title = entry.get("title", "").strip()
            company = entry.get("company", "").strip()
            summary = entry.get("summary", "").strip()

            if not title or not company:
                continue

            # Skip if already in DB
            if db.title_exists(title, company, source_name=entry.get("source_name", "")):
                continue

            is_launch = bool(entry.get("is_launch", False))
            is_top_co = bool(entry.get("is_top_company", False))

            impact = self.assign_impact(title, summary, is_launch, is_top_co)

            # For daily digest, skip truly low-signal content
            if impact == "low" and not is_top_co and not is_launch:
                continue

            category = assign_category(title, summary, company)

            db.insert_update(
                title=title,
                company=company,
                summary=summary or title,
                timestamp=entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                impact_level=impact,
                source_url=entry.get("source_url", ""),
                source_name=entry.get("source_name", ""),
                is_launch=is_launch,
                is_top_company=is_top_co,
                category=category,
            )
            count += 1

        logger.info("Stored %d new entries (from %d raw, %d deduped)", count, len(raw_entries), len(deduped))
        return count

    def process(self) -> list[dict]:
        """Get processed unsent entries from last 24h for digest."""
        db = get_db()
        entries = db.get_last_24h()
        logger.info("Pipeline: %d unsent entries from last 24h", len(entries))

        # Refine impact levels in memory (don't write back to avoid over-sending alerts)
        for e in entries:
            e["impact_level"] = self.assign_impact(
                e["title"], e["summary"],
                bool(e.get("is_launch")), bool(e.get("is_top_company"))
            )
            if not e.get("category"):
                e["category"] = assign_category(e["title"], e["summary"], e.get("company", ""))

        entries = self.deduplicate(entries)
        entries = self.filter_noise(entries)

        # Sort: launches from top companies first, then by impact
        entries.sort(key=lambda e: (
            0 if (e.get("is_launch") and e.get("is_top_company")) else 1,
            {"high": 0, "medium": 1, "low": 2}.get(e.get("impact_level", "low"), 2),
            e.get("timestamp", ""),
        ))

        logger.info("Pipeline: %d entries after filtering", len(entries))
        return entries

    def get_top_updates(self, limit: int = 50) -> list[dict]:
        """Get top updates for the daily digest."""
        db = get_db()
        entries = db.get_top_updates(limit=limit)

        for e in entries:
            e["impact_level"] = self.assign_impact(
                e["title"], e["summary"],
                bool(e.get("is_launch")), bool(e.get("is_top_company"))
            )
            if not e.get("category"):
                e["category"] = assign_category(e["title"], e["summary"], e.get("company", ""))

        return [e for e in entries if e["impact_level"] in ("high", "medium")]
