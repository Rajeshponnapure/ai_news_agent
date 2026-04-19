#!/usr/bin/env python3
"""
Send AI digest as a professional PDF report to email.
This generates a well-structured PDF with categorized sections, tech launches prioritized,
and sends it as an email with HTML body + PDF attachment.
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
    """Generate PDF report from real AI updates and send via email."""
    
    print("=" * 70)
    print("AI AGENT - PDF DIGEST GENERATOR (Email Delivery)")
    print("=" * 70)
    
    # Import modules
    from database.db import get_db
    from processing.pipeline import ProcessingPipeline
    from notifier.email_notifier import EmailNotifier
    from config.settings import settings
    
    # Check configuration
    print(f"\n📧 Email Recipient: {settings.EMAIL_RECIPIENT}")
    print(f"✉️  Email Sender: {settings.EMAIL_SENDER}")
    
    if not settings.EMAIL_ENABLED or not settings.EMAIL_PASSWORD:
        print("\n❌ ERROR: Email not configured!")
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
    # BUG-17 FIX: Use pipeline.process() which handles everything consistently
    print(f"\n🔍 Processing {len(entries)} entries...")
    pipeline = ProcessingPipeline()
    
    # Use the pipeline's own processing which assigns impact, deduplicates, and filters
    processed_entries = pipeline.process()
    print(f"   After processing: {len(processed_entries)} updates")
    
    if not processed_entries:
        # Fallback: if pipeline returns empty (all filtered), use raw entries
        print("   ⚠️ Pipeline filtered all entries, using raw entries instead")
        for entry in entries:
            refined = pipeline.assign_impact(entry["title"], entry["summary"])
            entry["impact_level"] = refined
        processed_entries = entries
    
    # Show category breakdown
    from reporting.pdf_generator import PDFReportGenerator
    generator = PDFReportGenerator()
    
    categorized = {}
    for u in processed_entries:
        cat = generator._get_category_for_update(u)
        categorized.setdefault(cat, 0)
        categorized[cat] += 1
    
    print("\n📊 Categories breakdown:")
    for cat, count in sorted(categorized.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count} updates")
    
    # Confirm before generating
    print(f"\n⚠️  This will:")
    print(f"   • Generate a professional PDF with {len(processed_entries)} updates")
    print(f"   • Prioritize tech launches at the top")
    print(f"   • Categorize by industry")
    print(f"   • Send email with HTML body + PDF attachment to: {settings.EMAIL_RECIPIENT}")
    print()
    
    # Auto-send after 5 seconds
    print("Starting in 5 seconds... (Ctrl+C to cancel)")
    time.sleep(5)
    
    # Generate and send
    print("\n" + "=" * 70)
    print("GENERATING & SENDING EMAIL DIGEST")
    print("=" * 70)
    
    notifier = EmailNotifier()
    success = notifier.send_digest(processed_entries)
    notifier.close()
    
    if success:
        print("\n" + "=" * 70)
        print("✅ SUCCESS! PDF digest delivered via email!")
        print("=" * 70)
        print(f"\n📧 Check email ({settings.EMAIL_RECIPIENT}) for:")
        print(f"   • Rich HTML email with all {len(processed_entries)} updates")
        print(f"   • PDF attachment for offline reading")
        print(f"\nThe email includes:")
        print(f"   • Professional HTML body with categorized updates")
        print(f"   • {len(categorized)} industry categories")
        print(f"   • Impact levels and summaries")
        print(f"   • Source links for all updates")
        print(f"   • Attached PDF report")
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED! Could not deliver email digest")
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
