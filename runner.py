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
from datetime import datetime, timezone, timedelta
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
    """Check DB for unalerted HIGH/MEDIUM impact events and send immediate alert.
    
    REAL-TIME RULES:
    - Check every 5 minutes for fresh updates
    - Only look back 2 hours (real-time only, no old news)
    - Include HIGH and MEDIUM priority items
    - STRICT deduplication: double-check alert_sent flag before sending
    - Send ALL new items (no limit) - user wants comprehensive updates
    
    Returns True if an alert was sent (or nothing to alert), False on send failure.
    """
    from database.db import get_db
    from notifier.email_notifier import EmailNotifier
    from config.settings import settings

    db = get_db()
    
    # Get all unalerted HIGH and MEDIUM items from last 2 hours (real-time updates only)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn = db._get_conn()
    try:
        rows = conn.execute(
            """
            SELECT * FROM updates
            WHERE alert_sent = 0
              AND impact_level IN ('high', 'medium')
              AND timestamp >= ?
            ORDER BY 
                CASE impact_level WHEN 'high' THEN 0 ELSE 1 END,
                timestamp DESC
            """,
            (cutoff,)
        ).fetchall()
        new_alerts = [dict(r) for r in rows]
    finally:
        conn.close()

    if not new_alerts:
        logger.info("Alert check: no new high-priority events to alert")
        print("✅ Alert check: nothing new to notify")
        return True

    # Double-check: verify these items are still unalerted (race condition protection)
    still_unalerted = []
    for item in new_alerts:
        conn = db._get_conn()
        try:
            row = conn.execute(
                "SELECT alert_sent FROM updates WHERE id = ?",
                (item["id"],)
            ).fetchone()
            if row and row["alert_sent"] == 0:
                still_unalerted.append(item)
        finally:
            conn.close()
    
    if not still_unalerted:
        logger.info("Alert check: all items already alerted (race condition avoided)")
        print("✅ Alert check: items already alerted")
        return True
    
    new_alerts = still_unalerted
    launches = [u for u in new_alerts if u.get("is_launch")]
    
    logger.info(
        "Alert check: %d HIGH priority items (%d launches)",
        len(new_alerts), len(launches)
    )

    print(f"\n🚨 Found {len(new_alerts)} NEW high-priority events to alert:")
    for u in new_alerts[:5]:
        flag = "🚀" if u.get("is_launch") else "📌"
        print(f"  {flag} [{u.get('impact_level','?').upper()}] {u.get('title','')[:80]}")
        print(f"       {u.get('company','')} | {u.get('category','')}")

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
