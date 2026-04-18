import asyncio
import logging
import signal
import sys
from pathlib import Path

from config.settings import settings
from scheduler import AgentScheduler
from database.db import get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_agent")


def ensure_data_dir():
    """Ensure the data directory exists for SQLite."""
    db_path = Path(settings.SQLITE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)


async def run():
    """Main entry point – starts the scheduler and keeps the process alive."""
    ensure_data_dir()

    # Initialize database (creates schema if needed)
    db = get_db()
    logger.info("Database initialized at %s", settings.SQLITE_PATH)

    # Create and start scheduler
    agent = AgentScheduler()
    agent.start()

    # Run an initial ingestion immediately on startup
    logger.info("Running initial ingestion...")
    try:
        count = await agent.ingestion_manager.run_async()
        logger.info("Initial ingestion complete: %d new entries", count)
    except Exception as e:
        logger.error("Initial ingestion failed: %s", e, exc_info=True)

    # Graceful shutdown handling
    loop = asyncio.get_event_loop()

    def _shutdown():
        logger.info("Shutdown signal received")
        agent.shutdown()
        loop.call_soon_threadsafe(loop.stop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    logger.info("🤖 AI Update Agent is running. Press Ctrl+C to stop.")

    # Keep the event loop running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        agent.shutdown()


def main():
    """CLI entry point."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")


if __name__ == "__main__":
    main()
