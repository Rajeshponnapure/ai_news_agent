#!/usr/bin/env python3
"""
runner.py — GitHub Actions / CLI entrypoint for AI News Agent.

Commands:
    python runner.py ingest        Run one ingestion cycle (fetch + store)
    python runner.py alert-check   Check for new launch events → send alert email
    python runner.py digest        Generate PDF + send daily digest email
    python runner.py ingest-alert  Ingest then immediately check for alerts (combined)
    python runner.py both          Ingest + digest (used by daily_digest.yml)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("runner")


def ensure_dirs():
    Path("data").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)


# ── Individual commands ───────────────────────────────────────────────────────

async def run_ingestion() -> int:
    """Fetch all sources and store new entries. Returns count of new entries."""
    from ingestion.manager import IngestionManager
    mgr = IngestionManager()
    try:
        count = await mgr.run_async()
        logger.info("Ingestion complete: %d new entries stored", count)
        return count
    finally:
        mgr.close()


def run_alert_check() -> bool:
    """Check DB for unalerted high-impact launch events and send immediate alert.
    
    Returns True if an alert was sent (or nothing to alert), False on send failure.
    This is called after EVERY ingestion cycle so alerts fire in near real-time.
    """
    from database.db import get_db
    from notifier.email_notifier import EmailNotifier
    from config.settings import settings

    db = get_db()
    new_alerts = db.get_new_alerts()

    if not new_alerts:
        logger.info("Alert check: no new events to alert")
        print("✅ Alert check: nothing new to notify")
        return True

    # Alert on ALL new updates (high, medium, low impact - everything)
    launches = [u for u in new_alerts if u.get("is_launch")]
    high_count = sum(1 for u in new_alerts if u.get("impact_level") == "high")
    medium_count = sum(1 for u in new_alerts if u.get("impact_level") == "medium")
    low_count = sum(1 for u in new_alerts if u.get("impact_level") == "low")
    
    logger.info(
        "Alert check: %d new items (%d launches, %d high, %d medium, %d low)",
        len(new_alerts), len(launches), high_count, medium_count, low_count
    )

    print(f"\n🚨 Found {len(new_alerts)} NEW events to alert:")
    for u in new_alerts[:5]:  # Show max 5 in logs
        flag = "🚀" if u.get("is_launch") else "📌"
        print(f"  {flag} [{u.get('impact_level','?').upper()}] {u.get('title','')[:80]}")
        print(f"       {u.get('company','')} | {u.get('category','')}")
    if len(new_alerts) > 5:
        print(f"  ... and {len(new_alerts) - 5} more")

    notifier = EmailNotifier()
    try:
        success = notifier.send_alert(new_alerts)
        if success:
            logger.info("Alert email sent for %d events", len(new_alerts))
            print(f"✅ Alert email sent: {len(new_alerts)} events → {settings.EMAIL_RECIPIENT}")
        else:
            logger.error("Alert email failed")
            print("❌ Alert email failed")
        return success
    finally:
        notifier.close()


def run_digest() -> bool:
    """Generate PDF + send full daily digest. Returns True on success."""
    from processing.pipeline import ProcessingPipeline
    from notifier.email_notifier import EmailNotifier

    pipeline = ProcessingPipeline()
    updates = pipeline.get_top_updates(limit=80)

    if not updates:
        logger.warning("No updates for digest — running emergency ingestion")
        count = asyncio.run(run_ingestion())
        logger.info("Emergency ingestion: %d entries", count)
        updates = pipeline.get_top_updates(limit=80)

    if not updates:
        logger.error("Still no updates after emergency ingestion")
        return False

    launches = sum(1 for u in updates if u.get("is_launch"))
    print(f"\n📊 Digest: {len(updates)} updates ({launches} launches), sending...")

    notifier = EmailNotifier()
    try:
        success = notifier.send_digest(updates)
        return success
    finally:
        notifier.close()


def run_cleanup():
    """Remove old entries from the database."""
    from database.db import get_db
    db = get_db()
    db.cleanup_old(days=3)  # Keep 3 days for context
    logger.info("Database cleanup complete (entries >3 days old removed)")
    print("🧹 Database cleaned up")


# ── Main entrypoint ───────────────────────────────────────────────────────────

def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "ingest":
        # Just run ingestion
        count = asyncio.run(run_ingestion())
        print(f"\n✅ Ingested {count} new entries")
        sys.exit(0 if count >= 0 else 1)

    elif command == "alert-check":
        # Just check for alerts (without running ingestion first)
        success = run_alert_check()
        sys.exit(0 if success else 1)

    elif command == "ingest-alert":
        # Ingest + immediately check for new alerts (used in ingest.yml)
        print("=== INGEST + ALERT CHECK ===")
        count = asyncio.run(run_ingestion())
        print(f"\n✅ Ingested {count} new entries")
        if count > 0:
            # Only check alerts if we actually got new entries
            success = run_alert_check()
        else:
            print("ℹ️  No new entries — skipping alert check")
            success = True
        sys.exit(0 if success else 1)

    elif command == "digest":
        # Just send the daily digest
        success = run_digest()
        sys.exit(0 if success else 1)

    elif command == "both":
        # Ingest + send digest (used in daily_digest.yml)
        print("=== INGEST + DIGEST ===")
        asyncio.run(run_ingestion())
        success = run_digest()
        sys.exit(0 if success else 1)

    elif command == "cleanup":
        run_cleanup()
        sys.exit(0)

    else:
        logger.error("Unknown command: %s", command)
        print(f"❌ Unknown command: {command}")
        print("Usage: python runner.py [ingest|alert-check|ingest-alert|digest|both|cleanup]")
        sys.exit(1)


if __name__ == "__main__":
    main()
