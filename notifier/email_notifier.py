"""
Email Notifier — two delivery modes:
  1. send_alert()  — immediate email when a major AI event is detected
  2. send_digest() — daily summary email with full PDF attachment
"""

import logging
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta

from config.settings import settings
from database.db import get_db

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Category display colors for HTML emails
CATEGORY_COLORS = {
    "🚀 AI LAUNCHES & RELEASES":   "#e74c3c",
    "💰 FINANCE & FINTECH AI":      "#2980b9",
    "📣 MARKETING & GROWTH AI":     "#8e44ad",
    "💻 AI CODING & DEVELOPER TOOLS": "#27ae60",
    "⚡ HARDWARE & INFRASTRUCTURE": "#e67e22",
    "🔬 RESEARCH & SCIENCE":        "#16a085",
    "📰 OTHER AI NEWS":             "#7f8c8d",
}

IMPACT_COLORS = {
    "high":   "#e74c3c",
    "medium": "#f39c12",
    "low":    "#95a5a6",
}

CATEGORY_ORDER = [
    "🚀 AI LAUNCHES & RELEASES",
    "💰 FINANCE & FINTECH AI",
    "📣 MARKETING & GROWTH AI",
    "💻 AI CODING & DEVELOPER TOOLS",
    "⚡ HARDWARE & INFRASTRUCTURE",
    "🔬 RESEARCH & SCIENCE",
    "📰 OTHER AI NEWS",
]


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


class EmailNotifier:
    """Delivers AI news via email — instant alerts and daily digests."""

    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY_SECONDS

    # ── SMTP core ────────────────────────────────────────────────────────────

    def _send_email(self, subject: str, html_body: str, plain_body: str,
                    pdf_path: str = None) -> bool:
        """Send email with optional PDF attachment."""
        if not settings.EMAIL_ENABLED:
            logger.error("Email disabled in settings")
            return False
        if not all([settings.EMAIL_SENDER, settings.EMAIL_PASSWORD, settings.EMAIL_RECIPIENT]):
            logger.error("Email credentials incomplete (sender/password/recipient)")
            return False

        msg = MIMEMultipart("mixed")
        msg["From"] = settings.EMAIL_SENDER
        msg["To"] = settings.EMAIL_RECIPIENT
        msg["Subject"] = subject

        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(plain_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(body_part)

        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    att = MIMEBase("application", "octet-stream")
                    att.set_payload(f.read())
                encoders.encode_base64(att)
                att.add_header("Content-Disposition",
                               f'attachment; filename="{os.path.basename(pdf_path)}"')
                msg.attach(att)
            except Exception as e:
                logger.error("PDF attach failed: %s", e)

        for attempt in range(1, self.max_retries + 1):
            try:
                if settings.EMAIL_SMTP_PORT == 465:
                    srv = smtplib.SMTP_SSL(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT)
                else:
                    srv = smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT)
                    srv.starttls()
                srv.login(settings.EMAIL_SENDER, settings.EMAIL_PASSWORD)
                srv.sendmail(settings.EMAIL_SENDER, settings.EMAIL_RECIPIENT, msg.as_string())
                srv.quit()
                logger.info("Email sent (attempt %d): %s", attempt, subject[:60])
                return True
            except Exception as e:
                logger.warning("Email attempt %d failed: %s", attempt, e)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        logger.error("Email delivery failed after %d attempts", self.max_retries)
        return False

    # ── ALERT EMAIL — real-time, compact, immediate ──────────────────────────

    def _build_alert_html(self, updates: list[dict], date_str: str) -> str:
        """Build a compact, punchy alert email for real-time events."""
        items_html = ""
        for u in updates:
            title   = _esc(u.get("title", ""))
            company = _esc(u.get("company", ""))
            summary = _esc(u.get("summary", ""))
            impact  = u.get("impact_level", "medium")
            url     = u.get("source_url", "")
            cat     = u.get("category", "📰 OTHER AI NEWS")
            is_launch = u.get("is_launch", False)

            badge_color = IMPACT_COLORS.get(impact, "#95a5a6")
            cat_color   = CATEGORY_COLORS.get(cat, "#7f8c8d")
            launch_tag  = '<span style="background:#e74c3c;color:#fff;padding:2px 7px;border-radius:3px;font-size:11px;margin-right:6px;font-weight:bold;">🚀 NEW LAUNCH</span>' if is_launch else ""

            link_html = f'<a href="{url}" style="color:#3498db;font-size:12px;text-decoration:none;">→ Read full story</a>' if url else ""

            # Summary only if different from title
            summary_html = f'<p style="margin:6px 0 0 0;color:#555;font-size:13px;line-height:1.5;">{summary}</p>' if summary and summary.strip() != title.strip() else ""

            items_html += f"""
            <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:14px;
                        border-left:4px solid {cat_color};box-shadow:0 1px 4px rgba(0,0,0,0.07);">
                <div style="margin-bottom:6px;">
                    {launch_tag}
                    <span style="background:{badge_color};color:#fff;padding:2px 8px;
                                 border-radius:3px;font-size:11px;font-weight:bold;">
                        {impact.upper()}
                    </span>
                    <span style="color:{cat_color};font-size:11px;margin-left:8px;font-weight:bold;">
                        {_esc(cat)}
                    </span>
                </div>
                <p style="margin:6px 0 4px 0;font-size:15px;font-weight:bold;color:#1a1a2e;">{title}</p>
                <p style="margin:0 0 6px 0;color:#7f8c8d;font-size:12px;">📌 {company}</p>
                {summary_html}
                <div style="margin-top:10px;">{link_html}</div>
            </div>"""

        count = len(updates)
        return f"""
        <html><head><meta charset="utf-8"></head>
        <body style="font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:20px;">
          <div style="max-width:640px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1a1a2e,#e74c3c);
                        color:#fff;padding:24px 28px;border-radius:12px 12px 0 0;">
              <div style="font-size:13px;opacity:0.8;margin-bottom:4px;">⚡ BREAKING AI UPDATE</div>
              <h1 style="margin:0 0 6px 0;font-size:22px;">
                🚨 {count} New AI {'Event' if count==1 else 'Events'} Detected
              </h1>
              <div style="opacity:0.85;font-size:13px;">{date_str}</div>
            </div>
            <div style="background:#fafafa;padding:20px 24px;border-radius:0 0 12px 12px;">
              <p style="color:#555;font-size:13px;margin:0 0 16px 0;">
                Major AI {'event' if count==1 else 'events'} just happened. Here's what you need to know:
              </p>
              {items_html}
              <div style="border-top:1px solid #eee;margin-top:20px;padding-top:14px;
                          color:#aaa;font-size:11px;text-align:center;">
                AI News Agent • Real-time alerts •
                Sources: Official blogs, RSS feeds, NewsAPI
              </div>
            </div>
          </div>
        </body></html>"""

    def _build_alert_plain(self, updates: list[dict], date_str: str) -> str:
        lines = [f"⚡ BREAKING AI UPDATE — {date_str}",
                 f"{len(updates)} new AI event(s) detected", "=" * 50, ""]
        for u in updates:
            lines.append(f"[{u.get('impact_level','?').upper()}] {u.get('title','')}")
            if u.get("company"):
                lines.append(f"  Company : {u['company']}")
            if u.get("summary") and u.get("summary") != u.get("title"):
                lines.append(f"  Summary : {u['summary'][:200]}")
            if u.get("source_url"):
                lines.append(f"  Link    : {u['source_url']}")
            lines.append("")
        return "\n".join(lines)

    def send_alert(self, updates: list[dict]) -> bool:
        """Send a real-time BREAKING alert email for new AI launch events.
        Called immediately after ingestion finds important new items.
        Does NOT attach a PDF — kept compact and fast."""
        if not updates:
            return True

        date_str = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
        count = len(updates)

        # Build subject with launch emoji for high-visibility
        companies = list(dict.fromkeys(u.get("company", "") for u in updates[:3]))
        company_str = ", ".join(c for c in companies if c)
        subject = f"🚨 AI Alert: {count} new {'launch' if count==1 else 'launches'} — {company_str}"

        html  = self._build_alert_html(updates, date_str)
        plain = self._build_alert_plain(updates, date_str)

        success = self._send_email(subject, html, plain)
        if success:
            # Mark all as alert_sent so we don't re-alert the same items
            db = get_db()
            ids = [u["id"] for u in updates if "id" in u]
            if ids:
                db.mark_alert_sent(ids)
            print(f"✅ Alert sent: {count} events → {settings.EMAIL_RECIPIENT}")
        else:
            print(f"❌ Alert failed for {count} events")
        return success

    # ── DIGEST EMAIL — daily full report with PDF ─────────────────────────────

    def _build_digest_html(self, updates: list[dict], date_str: str) -> str:
        """Rich HTML daily digest, categorized and sorted."""
        # Group by category
        cats: dict[str, list[dict]] = {}
        for u in updates:
            c = u.get("category", "📰 OTHER AI NEWS")
            cats.setdefault(c, []).append(u)

        sections = ""
        for cat in CATEGORY_ORDER:
            if cat not in cats:
                continue
            color   = CATEGORY_COLORS.get(cat, "#7f8c8d")
            entries = sorted(cats[cat],
                             key=lambda x: {"high":0,"medium":1,"low":2}.get(x.get("impact_level","low"),2))
            items = ""
            for u in entries:
                title   = _esc(u.get("title", ""))
                company = _esc(u.get("company", ""))
                summary = _esc(u.get("summary", ""))
                impact  = u.get("impact_level", "medium")
                url     = u.get("source_url", "")
                badge   = IMPACT_COLORS.get(impact, "#95a5a6")
                launch_tag = '<span style="color:#e74c3c;font-weight:bold;">🚀 LAUNCH &nbsp;</span>' \
                             if u.get("is_launch") else ""
                summary_html = f'<div style="color:#666;font-size:12px;margin-top:5px;line-height:1.5;">{summary}</div>' \
                               if summary and summary.strip() != title.strip() else ""
                link_html = f'<a href="{url}" style="color:#3498db;font-size:11px;">→ Read more</a>' if url else ""
                items += f"""
                <div style="padding:12px 0;border-bottom:1px solid #f0f0f0;">
                    {launch_tag}<span style="background:{badge};color:#fff;padding:1px 7px;
                    border-radius:3px;font-size:10px;font-weight:bold;">{impact.upper()}</span>
                    <span style="margin-left:8px;font-size:12px;color:#888;">{company}</span>
                    <div style="font-size:14px;font-weight:bold;color:#1a1a2e;margin-top:5px;">{title}</div>
                    {summary_html}
                    <div style="margin-top:6px;">{link_html}</div>
                </div>"""

            sections += f"""
            <div style="margin-bottom:24px;">
                <div style="background:{color};color:#fff;padding:10px 16px;
                            border-radius:8px;font-weight:bold;font-size:15px;margin-bottom:2px;">
                    {_esc(cat)} &nbsp;<span style="opacity:0.8;font-size:12px;font-weight:normal;">
                    ({len(entries)} update{'s' if len(entries)!=1 else ''})</span>
                </div>
                <div style="background:#fff;border-radius:0 0 8px 8px;
                            padding:0 16px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                    {items}
                </div>
            </div>"""

        toc = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;">'
            f'<span>{_esc(c)}</span><span style="color:#888;">{len(cats[c])}</span></div>'
            for c in CATEGORY_ORDER if c in cats
        )

        return f"""
        <html><head><meta charset="utf-8"></head>
        <body style="font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:20px;">
          <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;
                      box-shadow:0 2px 12px rgba(0,0,0,0.1);overflow:hidden;">
            <div style="background:linear-gradient(135deg,#1a1a2e,#3498db);
                        color:#fff;padding:32px;text-align:center;">
              <h1 style="margin:0 0 8px;font-size:28px;">🚀 AI Update Digest</h1>
              <div style="opacity:0.9;font-size:16px;">{date_str}</div>
              <div style="margin-top:14px;opacity:0.85;font-size:13px;">
                📊 {len(updates)} updates · {len(cats)} categories · AI launches prioritized
              </div>
            </div>
            <div style="padding:20px 28px;background:#fafafa;border-bottom:1px solid #eee;">
              <div style="font-weight:bold;color:#2c3e50;margin-bottom:10px;">📋 Contents</div>
              {toc}
            </div>
            <div style="padding:24px 28px;">
              {sections}
            </div>
            <div style="padding:16px 28px;text-align:center;color:#999;font-size:11px;
                        background:#fafafa;border-top:1px solid #eee;">
              AI News Agent · {date_str} · Sources: OpenAI, Anthropic, Google, Microsoft & 50+ more
              <br>📎 Full PDF report attached
            </div>
          </div>
        </body></html>"""

    def _build_digest_plain(self, updates: list[dict], date_str: str) -> str:
        cats: dict[str, list] = {}
        for u in updates:
            cats.setdefault(u.get("category", "📰 OTHER AI NEWS"), []).append(u)
        lines = [f"AI Update Digest — {date_str}", f"Total: {len(updates)} updates", "="*50]
        for cat in CATEGORY_ORDER:
            if cat not in cats:
                continue
            lines += ["", cat, "-"*40]
            for u in cats[cat]:
                lines.append(f"\n  [{u.get('impact_level','?').upper()}] {u.get('title','')}")
                lines.append(f"  {u.get('company','')} | {u.get('source_url','')}")
        return "\n".join(lines)

    def send_digest(self, updates: list[dict]) -> bool:
        """Send full daily digest email with HTML + PDF attachment."""
        if not updates:
            logger.warning("No updates to send in digest")
            return True

        date_str = datetime.now(IST).strftime("%d %b %Y")

        # Generate PDF
        pdf_path = None
        try:
            from reporting.pdf_generator import generate_pdf_report
            print(f"\n📄 Generating PDF for {len(updates)} updates...")
            pdf_path = generate_pdf_report(updates)
            if pdf_path and os.path.exists(pdf_path):
                print(f"✅ PDF ready: {os.path.basename(pdf_path)}")
        except Exception as e:
            logger.error("PDF generation failed: %s", e, exc_info=True)
            print(f"⚠️  PDF failed: {e}")

        html  = self._build_digest_html(updates, date_str)
        plain = self._build_digest_plain(updates, date_str)

        launches = sum(1 for u in updates if u.get("is_launch"))
        subject  = (f"🚀 AI Digest — {date_str} | "
                    f"{len(updates)} updates · {launches} launches")

        print(f"\n📧 Sending digest to {settings.EMAIL_RECIPIENT}...")
        success = self._send_email(subject, html, plain, pdf_path)

        if success:
            db = get_db()
            ids = [u["id"] for u in updates if "id" in u]
            if ids:
                db.mark_digest_sent(ids)
                db.mark_alert_sent(ids)     # avoid re-alerting digested items
            print(f"✅ Digest sent: {len(updates)} updates, {launches} launches")
        else:
            print("❌ Digest send failed")
        return success

    def close(self):
        pass
