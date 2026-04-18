import logging
import re
from datetime import datetime, timezone

from database.db import get_db

logger = logging.getLogger(__name__)

# Keywords that signal high-impact updates — covers all AI domains
HIGH_IMPACT_KEYWORDS = [
    # ── Major model releases ──
    "gpt-5", "gpt-4", "gpt4", "claude 4", "claude4", "gemini 2", "gemini2",
    "llama 4", "llama4", "new model", "model release", "launch",
    "breakthrough", "state of the art", "sota", "frontier model",
    "foundation model", "major release", "game changer",
    # ── Chips & hardware ──
    "h100", "h200", "b200", "blackwell", "nvidia", "new gpu", "new chip",
    # ── Startups & funding ──
    "series a", "series b", "ipo", "acquisition", "merger", "billion",
    # ── Business impact ──
    "enterprise ai", "ai strategy", "ai transformation", "ai adoption",
    # ── Healthcare breakthroughs ──
    "ai drug", "ai diagnosis", "clinical trial", "fda approval",
    # ── Safety & regulation ──
    "ai regulation", "ai act", "ai safety", "executive order",
]

MEDIUM_IMPACT_KEYWORDS = [
    "update", "upgrade", "improvement", "fine-tune", "finetune",
    "benchmark", "evaluation", "api", "sdk", "open source",
    "weights released", "checkpoint", "research paper",
    "funding", "investment", "partnership", "collaboration",
    "ai startup", "new feature", "integration", "performance",
    "gpu", "inference", "training", "multimodal", "agent",
    "rag", "embedding", "chatbot", "assistant", "code generation",
    "autonomous", "robotics", "self-driving", "healthcare ai",
    "finance ai", "fintech", "ai banking", "ai coding",
]

EXCLUDE_KEYWORDS = [
    "opinion", "editorial", "podcast", "weekly roundup", "newsletter",
    "hiring", "job posting", "career", "salary",
    "stock price", "earnings", "dividend",
    "politics", "election", "campaign",
    "celebrity", "gossip", "sports",
]


class ProcessingPipeline:
    """Processes raw entries: assigns impact level, deduplicates, filters noise."""

    def assign_impact(self, title: str, summary: str) -> str:
        text = f"{title} {summary}".lower()

        # Check exclusions first
        for kw in EXCLUDE_KEYWORDS:
            if kw in text:
                return "low"

        for kw in HIGH_IMPACT_KEYWORDS:
            if kw in text:
                return "high"

        for kw in MEDIUM_IMPACT_KEYWORDS:
            if kw in text:
                return "medium"

        return "low"

    def _normalize(self, text: str) -> str:
        """Normalize text for dedup comparison."""
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def deduplicate(self, entries: list[dict]) -> list[dict]:
        """Remove duplicate entries based on normalized title+company."""
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
        """Remove entries that are purely noise/opinion."""
        filtered = []
        for entry in entries:
            text = f"{entry['title']} {entry.get('summary', '')}".lower()
            exclude_count = sum(1 for kw in EXCLUDE_KEYWORDS if kw in text)
            if exclude_count >= 2:
                logger.debug("Filtered noise: %s", entry["title"][:60])
                continue
            filtered.append(entry)
        return filtered

    def process(self) -> list[dict]:
        """Run the full pipeline on stored entries from the last 24h."""
        db = get_db()

        # Get unsent entries from last 24h
        entries = db.get_last_24h()
        logger.info("Pipeline processing %d entries", len(entries))

        # Assign impact levels to entries that don't have one yet
        # (entries from ingestion have 'medium' default; refine here)
        for entry in entries:
            refined_impact = self.assign_impact(entry["title"], entry["summary"])
            entry["impact_level"] = refined_impact

        # Deduplicate
        entries = self.deduplicate(entries)
        logger.info("After dedup: %d entries", len(entries))

        # Filter noise
        entries = self.filter_noise(entries)
        logger.info("After noise filter: %d entries", len(entries))

        # Sort by impact then recency
        impact_order = {"high": 0, "medium": 1, "low": 2}
        entries.sort(
            key=lambda e: (impact_order.get(e["impact_level"], 2), e["timestamp"]),
        )

        return entries

    def get_top_updates(self, limit: int = 10) -> list[dict]:
        """Get top updates for the daily digest."""
        entries = self.process()
        # Prioritize high/medium impact
        top = [e for e in entries if e["impact_level"] in ("high", "medium")]
        if len(top) < limit:
            low = [e for e in entries if e["impact_level"] == "low"]
            top.extend(low[: limit - len(top)])
        return top[:limit]
