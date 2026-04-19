import logging
import asyncio

from ingestion.rss_ingestor import RSSIngestor
from ingestion.blog_ingestor import BlogIngestor
from ingestion.github_ingestor import GitHubIngestor
from ingestion.newsapi_ingestor import NewsAPIIngestor
from processing.pipeline import ProcessingPipeline

logger = logging.getLogger(__name__)


class IngestionManager:
    """Orchestrates all ingestion sources — runs them all and passes to pipeline."""

    def __init__(self):
        self.rss = RSSIngestor()
        self.blog = BlogIngestor()
        self.github = GitHubIngestor()
        self.newsapi = NewsAPIIngestor()
        self.pipeline = ProcessingPipeline()

    def _run_ingestors(self) -> list[dict]:
        """Run all ingestors, return combined raw entries."""
        all_entries = []
        for name, ingestor in [
            ("RSS", self.rss),
            ("Blog", self.blog),
            ("GitHub", self.github),
            ("NewsAPI", self.newsapi),
        ]:
            try:
                entries = ingestor.ingest()
                logger.info("%s ingestor: %d raw entries", name, len(entries))
                all_entries.extend(entries)
            except Exception as e:
                logger.error("%s ingestor failed: %s", name, e, exc_info=True)
        return all_entries

    def run(self) -> int:
        """Run all ingestors and store processed entries. Returns count of new entries."""
        logger.info("=== Ingestion cycle started ===")
        raw_entries = self._run_ingestors()
        logger.info("Total raw entries from all sources: %d", len(raw_entries))

        # Pipeline handles dedup, impact assignment, category, and storage
        stored = self.pipeline.ingest_and_store(raw_entries)
        logger.info("=== Ingestion complete: %d new entries stored ===", stored)
        return stored

    async def run_async(self) -> int:
        """Async wrapper for event loop compatibility."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)

    def close(self):
        self.rss.close()
        self.blog.close()
        self.github.close()
        self.newsapi.close()
