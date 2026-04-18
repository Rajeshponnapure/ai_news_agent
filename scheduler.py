import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from ingestion.manager import IngestionManager
from processing.pipeline import ProcessingPipeline
from notifier.whatsapp import WhatsAppNotifier
from database.db import get_db

logger = logging.getLogger(__name__)

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))


class AgentScheduler:
    """Schedules ingestion, processing, and notification jobs."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self.ingestion_manager = IngestionManager()
        self.pipeline = ProcessingPipeline()
        self.notifier = WhatsAppNotifier()

    async def _ingestion_job(self):
        """Periodic ingestion job – runs every N minutes."""
        logger.info("Scheduled ingestion job triggered")
        try:
            count = await self.ingestion_manager.run_async()
            logger.info("Ingestion job complete: %d new entries", count)
        except Exception as e:
            logger.error("Ingestion job failed: %s", e, exc_info=True)

    async def _compile_and_send_job(self):
        """Daily job at 05:55 IST – compile top updates and send at 06:00 IST."""
        logger.info("Compile-and-send job triggered")

        # Run one final ingestion before compiling
        try:
            await self.ingestion_manager.run_async()
        except Exception as e:
            logger.error("Pre-compile ingestion failed: %s", e, exc_info=True)

        # Get top updates
        try:
            updates = self.pipeline.get_top_updates(limit=10)
            logger.info("Compiled %d top updates for digest", len(updates))
        except Exception as e:
            logger.error("Pipeline processing failed: %s", e, exc_info=True)
            updates = []

        # Send digest
        try:
            success = self.notifier.send_digest(updates)
            if success:
                logger.info("Digest sent successfully")
            else:
                logger.error("Digest send failed after retries")
        except Exception as e:
            logger.error("Digest send error: %s", e, exc_info=True)

        # Cleanup old entries
        try:
            db = get_db()
            db.cleanup_old(days=7)
            logger.info("Old entries cleaned up")
        except Exception as e:
            logger.error("Cleanup failed: %s", e, exc_info=True)

    def _parse_cron_time(self, time_str: str) -> dict:
        """Parse HH:MM string into cron hour/minute for IST."""
        parts = time_str.strip().split(":")
        return {"hour": int(parts[0]), "minute": int(parts[1])}

    def start(self):
        """Configure and start the scheduler."""
        # Ingestion: every N minutes
        interval = settings.INGESTION_INTERVAL_MINUTES
        self.scheduler.add_job(
            self._ingestion_job,
            trigger=IntervalTrigger(minutes=interval),
            id="ingestion",
            name="Ingestion Worker",
            max_instances=1,
            misfire_grace_time=120,
        )
        logger.info("Ingestion job scheduled every %d minutes", interval)

        # Daily compile + send at configured IST time
        send_time = self._parse_cron_time(settings.SEND_TIME_IST)
        self.scheduler.add_job(
            self._compile_and_send_job,
            trigger=CronTrigger(
                hour=send_time["hour"],
                minute=send_time["minute"],
                timezone=IST,
            ),
            id="compile_send",
            name="Compile & Send Digest",
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info(
            "Digest job scheduled daily at %02d:%02d IST",
            send_time["hour"],
            send_time["minute"],
        )

        self.scheduler.start()
        logger.info("Scheduler started")

    def shutdown(self):
        """Gracefully shut down the scheduler and resources."""
        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=False)
        self.ingestion_manager.close()
        self.notifier.close()
        logger.info("Scheduler shut down complete")
