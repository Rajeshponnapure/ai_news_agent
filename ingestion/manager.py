import logging
import asyncio
from typing import Optional

from ingestion.rss_ingestor import RSSIngestor
from ingestion.blog_ingestor import BlogIngestor
from ingestion.github_ingestor import GitHubIngestor
from ingestion.newsapi_ingestor import NewsAPIIngestor
from database.db import get_db

logger = logging.getLogger(__name__)


class IngestionManager:
    """Orchestrates all ingestion sources and writes to the database."""

    def __init__(self):
        self.rss = RSSIngestor()
        self.blog = BlogIngestor()
        self.github = GitHubIngestor()
        self.newsapi = NewsAPIIngestor()

    def _run_ingestors(self) -> list[dict]:
        all_entries = []

        for name, ingestor in [("RSS", self.rss), ("Blog", self.blog), ("GitHub", self.github), ("NewsAPI", self.newsapi)]:
            try:
                entries = ingestor.ingest()
                logger.info("%s ingestor returned %d entries", name, len(entries))
                all_entries.extend(entries)
            except Exception as e:
                logger.error("%s ingestor failed: %s", name, e, exc_info=True)

        return all_entries

    def _store_entries(self, entries: list[dict]) -> int:
        db = get_db()
        stored = 0
        for entry in entries:
            try:
                # Skip if title+company already exists (dedup at DB level)
                if db.title_exists(entry["title"], entry["company"]):
                    continue
                entry_id = db.insert_update(
                    title=entry["title"],
                    company=entry["company"],
                    summary=entry["summary"],
                    timestamp=entry["timestamp"],
                    impact_level=entry.get("impact_level", "medium"),
                    source_url=entry["source_url"],
                    source_name=entry.get("source_name", ""),
                )
                stored += 1
                logger.debug("Stored entry %s: %s", entry_id[:8], entry["title"][:60])
            except Exception as e:
                logger.error("Failed to store entry '%s': %s", entry.get("title", "?"), e)
        return stored

    def run(self) -> int:
        """Run all ingestors and store new entries. Returns count of new entries stored."""
        logger.info("=== Ingestion cycle started ===")
        entries = self._run_ingestors()
        logger.info("Total raw entries: %d", len(entries))
        stored = self._store_entries(entries)
        logger.info("New entries stored: %d", stored)
        return stored

    async def run_async(self) -> int:
        """Async wrapper – runs ingestion in a thread pool so it doesn't block the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)

    def close(self):
        self.rss.close()
        self.blog.close()
        self.github.close()
        self.newsapi.close()
