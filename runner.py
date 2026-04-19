#!/usr/bin/env python3
"""
runner.py — GitHub Actions entrypoint for AI News Agent.

Usage:
    python runner.py ingest      # Run one ingestion cycle
    python runner.py digest      # Generate and send daily PDF digest
    python runner.py both        # Ingest then send digest
"""

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("runner")


def ensure_dirs():
    """Create necessary directories."""
    Path("data").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)


async def run_ingestion() -> int:
    """Run one ingestion cycle and return count of new entries."""
    from ingestion.manager import IngestionManager
    mgr = IngestionManager()
    try:
        count = await mgr.run_async()
        logger.info("Ingestion complete: %d new entries stored", count)
        return count
    finally:
        mgr.close()


def run_digest() -> bool:
    """Generate PDF and send email digest. Returns True on success."""
    from processing.pipeline import ProcessingPipeline
    from notifier.email_notifier import EmailNotifier

    pipeline = ProcessingPipeline()
    updates = pipeline.get_top_updates(limit=80)

    if not updates:
        logger.warning("No updates found for digest. Running emergency ingestion...")
        count = asyncio.run(run_ingestion())
        logger.info("Emergency ingestion: %d entries", count)
        updates = pipeline.get_top_updates(limit=80)

    if not updates:
        logger.error("No updates available even after ingestion. Skipping digest.")
        return False

    logger.info("Sending digest with %d updates...", len(updates))
    notifier = EmailNotifier()
    try:
        success = notifier.send_digest(updates)
        if success:
            logger.info("✅ Digest sent successfully!")
        else:
            logger.error("❌ Digest send failed after all retries")
        return success
    finally:
        notifier.close()


def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        print("Usage: python runner.py [ingest|digest|both]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "ingest":
        count = asyncio.run(run_ingestion())
        sys.exit(0 if count >= 0 else 1)

    elif command == "digest":
        success = run_digest()
        sys.exit(0 if success else 1)

    elif command == "both":
        asyncio.run(run_ingestion())
        success = run_digest()
        sys.exit(0 if success else 1)

    else:
        logger.error("Unknown command: %s. Use: ingest | digest | both", command)
        sys.exit(1)


if __name__ == "__main__":
    main()
