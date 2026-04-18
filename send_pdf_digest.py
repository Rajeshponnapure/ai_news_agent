#!/usr/bin/env python3
"""
Send REAL AI digest as a professional PDF report to WhatsApp + Email.
This generates a well-structured PDF with categorized sections, tech launches prioritized.
"""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def send_pdf_digest():
    """Generate PDF report from real AI updates and send via WhatsApp + Email."""
    
    print("=" * 70)
    print("AI AGENT - PDF DIGEST GENERATOR")
    print("=" * 70)
    
    # Import modules
    from database.db import get_db
    from processing.pipeline import ProcessingPipeline
    from notifier.whatsapp import WhatsAppNotifier
    from config.settings import settings
    
    # Check configuration
    print(f"\n📱 WhatsApp Number: {settings.WHATSAPP_DIRECT_PHONE}")
    print(f"📧 Email Recipient: {settings.EMAIL_RECIPIENT}")
    print(f"✉️  Email Sender: {settings.EMAIL_SENDER}")
    
    if not settings.EMAIL_ENABLED or not settings.EMAIL_PASSWORD:
        print("\n❌ ERROR: Email not configured! PDF can only be sent via email.")
        print("   Please set EMAIL_ENABLED=true and EMAIL_PASSWORD in .env")
        return False
    
    # Get database
    print("\n📊 Fetching AI updates from database...")
    db = get_db()
    
    # Get last 24h of updates
    entries = db.get_last_24h()
    print(f"   Found {len(entries)} updates in last 24h")
    
    if not entries:
        print("\n⚠️  No updates found! Running ingestion first...")
        from ingestion.manager import IngestionManager
        mgr = IngestionManager()
        count = mgr.run()
        mgr.close()
        print(f"   Ingested {count} new entries")
        
        # Try again
        entries = db.get_last_24h()
        print(f"   Now have {len(entries)} updates")
    
    if not entries:
        print("\n❌ No updates available to generate PDF")
        return False
    
    # Process entries (assign impact, dedup, filter)
    print(f"\n🔍 Processing {len(entries)} entries...")
    pipeline = ProcessingPipeline()
    
    for entry in entries:
        refined = pipeline.assign_impact(entry["title"], entry["summary"])
        entry["impact_level"] = refined
    
    entries = pipeline.deduplicate(entries)
    entries = pipeline.filter_noise(entries)
    
    print(f"   After dedup/filter: {len(entries)} updates")
    
    # Show category breakdown
    from reporting.pdf_generator import PDFReportGenerator
    generator = PDFReportGenerator()
    
    categorized = {}
    for u in entries:
        cat = generator._get_category_for_update(u)
        if cat not in categorized:
            categorized[cat] = 0
        categorized[cat] += 1
    
    print("\n📊 Categories breakdown:")
    for cat, count in sorted(categorized.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count} updates")
    
    # Confirm before generating
    print(f"\n⚠️  This will:")
    print(f"   • Generate a professional PDF with {len(entries)} updates")
    print(f"   • Prioritize tech launches at the top")
    print(f"   • Categorize by industry")
    print(f"   • Send WhatsApp notification")
    print(f"   • Email PDF to: {settings.EMAIL_RECIPIENT}")
    print()
    
    # Auto-send after 5 seconds
    print("Starting in 5 seconds... (Ctrl+C to cancel)")
    time.sleep(5)
    
    # Generate and send PDF
    print("\n" + "=" * 70)
    print("GENERATING & SENDING PDF DIGEST")
    print("=" * 70)
    
    notifier = WhatsAppNotifier()
    success = notifier.send_pdf_digest(entries)
    notifier.close()
    
    if success:
        print("\n" + "=" * 70)
        print("✅ SUCCESS! PDF digest delivered!")
        print("=" * 70)
        print(f"\n📱 Check WhatsApp for notification")
        print(f"📧 Check email ({settings.EMAIL_RECIPIENT}) for PDF attachment")
        print(f"\nThe PDF includes:")
        print(f"   • Professional cover page")
        print(f"   • Table of contents")
        print(f"   • Tech launches prioritized")
        print(f"   • {len(categorized)} industry categories")
        print(f"   • Impact levels and summaries")
        print(f"   • Source links for all updates")
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED! Could not deliver PDF digest")
        print("=" * 70)
        return False
    
    return True


if __name__ == "__main__":
    try:
        success = send_pdf_digest()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)
