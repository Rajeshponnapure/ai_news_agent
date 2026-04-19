"""Email-only notifier — sends AI digest with HTML body + PDF attachment.

Replaces the old WhatsApp-based notifier. All delivery goes through SMTP email.
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


class EmailNotifier:
    """Sends AI digest via email with HTML body + PDF attachment."""

    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY_SECONDS

    # ── Category definitions for organizing updates ──────────────────────────

    CATEGORIES = {
        "💰 FINANCE & BUSINESS": [
            "finance", "banking", "fintech", "trading", "investment", "stock",
            "economy", "market", "revenue", "profit", "ipo", "acquisition",
            "valuation", "funding", "startup", "enterprise", "business",
            "corporate", "bank", "wall street", "imf", "federal reserve",
            "economist", "financial", "commercial", "industry"
        ],
        "🏥 MEDICAL & HEALTHCARE": [
            "healthcare", "medical", "health", "drug", "diagnosis", "clinical",
            "hospital", "patient", "pharma", "biotech", "biology", "protein",
            "dna", "genome", "therapy", "treatment", "disease", "medicine",
            "doctor", "fda", "trial", "vaccine", "mental health"
        ],
        "💻 CODING & DEVELOPMENT": [
            "coding", "programming", "developer", "devops", "software",
            "github", "code", "debugging", "ide", "api", "sdk", "framework",
            "library", "package", "npm", "pypi", "repository", "commit",
            "pull request", "release", "version"
        ],
        "🤖 AI TECH & MODELS": [
            "gpt", "claude", "gemini", "llama", "mistral", "model", "llm",
            "transformer", "neural", "deep learning", "machine learning",
            "benchmark", "training", "inference", "dataset", "weights",
            "checkpoint", "multimodal", "diffusion", "generative ai"
        ],
        "🔧 INDUSTRIAL & MANUFACTURING": [
            "manufacturing", "factory", "robotics", "automation", "industrial",
            "supply chain", "logistics", "warehouse", "production", "assembly",
            "quality control", "predictive maintenance", "iot", "sensor"
        ],
        "🚗 AUTONOMOUS & VEHICLES": [
            "autonomous", "self-driving", "vehicle", "car", "tesla", "waymo",
            "transportation", "mobility", "drone", "uav", "aviation",
            "shipping", "delivery", "navigation"
        ],
        "🔬 RESEARCH & SCIENCE": [
            "research", "paper", "study", "arxiv", "publication", "academic",
            "university", "lab", "scientific", "discovery", "breakthrough",
            "physics", "chemistry", "mathematics", "quantum"
        ],
        "⚡ HARDWARE & CHIPS": [
            "nvidia", "gpu", "tpu", "chip", "hardware", "cuda", "semiconductor",
            "processor", "cpu", "h100", "h200", "blackwell", "data center",
            "server", "compute", "accelerator"
        ],
        "📱 GENERAL TECH": [
            "tech", "technology", "app", "software", "platform", "digital",
            "internet", "cloud", "aws", "azure", "google cloud", "saas"
        ],
    }

    CATEGORY_PRIORITY = [
        "💰 FINANCE & BUSINESS",
        "🏥 MEDICAL & HEALTHCARE",
        "💻 CODING & DEVELOPMENT",
        "🤖 AI TECH & MODELS",
        "🔧 INDUSTRIAL & MANUFACTURING",
        "🚗 AUTONOMOUS & VEHICLES",
        "🔬 RESEARCH & SCIENCE",
        "⚡ HARDWARE & CHIPS",
        "📱 GENERAL TECH",
        "📰 OTHER AI NEWS",
    ]

    def _categorize(self, update: dict) -> str:
        """Determine which category an update belongs to."""
        text = f"{update.get('title', '')} {update.get('summary', '')} {update.get('company', '')}".lower()

        scores = {}
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score

        if not scores:
            return "📰 OTHER AI NEWS"

        return max(scores, key=scores.get)

    # ── HTML email body generation ───────────────────────────────────────────

    def _build_html_body(self, updates: list[dict], date_str: str) -> str:
        """Build a rich HTML email body with all updates categorized."""

        # Group by category
        categorized: dict[str, list[dict]] = {}
        for u in updates:
            cat = self._categorize(u)
            categorized.setdefault(cat, []).append(u)

        # Category colors (without emojis for CSS)
        cat_colors = {
            "💰 FINANCE & BUSINESS": "#2980b9",
            "🏥 MEDICAL & HEALTHCARE": "#e74c3c",
            "💻 CODING & DEVELOPMENT": "#2ecc71",
            "🤖 AI TECH & MODELS": "#9b59b6",
            "🔧 INDUSTRIAL & MANUFACTURING": "#e67e22",
            "🚗 AUTONOMOUS & VEHICLES": "#3498db",
            "🔬 RESEARCH & SCIENCE": "#1abc9c",
            "⚡ HARDWARE & CHIPS": "#f1c40f",
            "📱 GENERAL TECH": "#95a5a6",
            "📰 OTHER AI NEWS": "#bdc3c7",
        }

        impact_colors = {
            "high": "#e74c3c",
            "medium": "#f39c12",
            "low": "#95a5a6",
        }

        # Build HTML
        html_parts = [f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; color: #333; margin: 0; padding: 20px; }}
                .container {{ max-width: 700px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #2c3e50, #3498db); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0 0 5px 0; font-size: 28px; }}
                .header .date {{ font-size: 16px; opacity: 0.9; }}
                .header .stats {{ margin-top: 15px; font-size: 14px; opacity: 0.8; }}
                .toc {{ padding: 20px 30px; background: #fafafa; border-bottom: 1px solid #eee; }}
                .toc h2 {{ color: #2c3e50; font-size: 18px; margin: 0 0 10px 0; }}
                .toc-item {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 14px; }}
                .category-section {{ padding: 20px 30px; border-bottom: 1px solid #f0f0f0; }}
                .category-header {{ padding: 8px 15px; color: white; font-size: 16px; font-weight: bold; border-radius: 6px; margin-bottom: 15px; }}
                .update-card {{ background: #fafafa; border-radius: 8px; padding: 15px; margin-bottom: 12px; border-left: 4px solid #ddd; }}
                .update-title {{ font-size: 15px; font-weight: bold; color: #2c3e50; margin-bottom: 5px; }}
                .update-meta {{ font-size: 12px; color: #7f8c8d; margin-bottom: 8px; }}
                .update-summary {{ font-size: 13px; color: #555; line-height: 1.5; }}
                .impact-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; color: white; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
                .source-link {{ color: #3498db; text-decoration: none; font-size: 12px; }}
                .source-link:hover {{ text-decoration: underline; }}
                .footer {{ padding: 20px 30px; text-align: center; color: #95a5a6; font-size: 12px; background: #fafafa; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 AI Update Digest</h1>
                    <div class="date">{date_str}</div>
                    <div class="stats">📊 {len(updates)} updates across {len(categorized)} categories</div>
                </div>
        """]

        # Table of Contents
        html_parts.append('<div class="toc"><h2>📋 Contents</h2>')
        for cat in self.CATEGORY_PRIORITY:
            if cat in categorized:
                count = len(categorized[cat])
                html_parts.append(f'<div class="toc-item"><span>{cat}</span><span>{count} items</span></div>')
        html_parts.append('</div>')

        # Category sections
        for cat in self.CATEGORY_PRIORITY:
            if cat not in categorized:
                continue

            color = cat_colors.get(cat, "#95a5a6")
            updates_in_cat = categorized[cat]

            # Sort by impact
            impact_order = {"high": 0, "medium": 1, "low": 2}
            updates_in_cat.sort(key=lambda u: impact_order.get(u.get("impact_level", "low"), 2))

            html_parts.append(f'<div class="category-section">')
            html_parts.append(f'<div class="category-header" style="background: {color};">{cat} ({len(updates_in_cat)})</div>')

            for u in updates_in_cat:
                title = u.get("title", "No Title")
                company = u.get("company", "Unknown")
                summary = u.get("summary", "")
                impact = u.get("impact_level", "medium")
                url = u.get("source_url", "")
                impact_color = impact_colors.get(impact, "#95a5a6")

                html_parts.append(f'''
                <div class="update-card" style="border-left-color: {color};">
                    <div class="update-title">{self._escape_html(title)}</div>
                    <div class="update-meta">
                        <span class="impact-badge" style="background: {impact_color};">{impact}</span>
                        &nbsp; {self._escape_html(company)}
                    </div>
                    {"<div class='update-summary'>" + self._escape_html(summary) + "</div>" if summary and summary != title else ""}
                    {"<a class='source-link' href='" + url + "'>🔗 Read more</a>" if url else ""}
                </div>
                ''')

            html_parts.append('</div>')

        # Footer
        html_parts.append(f"""
                <div class="footer">
                    <p>Generated by AI Agent | {date_str}</p>
                    <p>Sources: NewsAPI, GitHub Releases, RSS Feeds, Tech Blogs</p>
                    <p>📎 Full PDF report attached for offline reading</p>
                </div>
            </div>
        </body>
        </html>
        """)

        return "\n".join(html_parts)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    def _build_plain_body(self, updates: list[dict], date_str: str) -> str:
        """Build a plain-text version of the digest."""
        lines = [
            f"AI Update Digest - {date_str}",
            f"Total: {len(updates)} updates",
            "=" * 50,
            "",
        ]

        # Group by category
        categorized: dict[str, list[dict]] = {}
        for u in updates:
            cat = self._categorize(u)
            categorized.setdefault(cat, []).append(u)

        for cat in self.CATEGORY_PRIORITY:
            if cat not in categorized:
                continue
            lines.append(f"\n{cat}")
            lines.append("-" * 40)
            for u in categorized[cat]:
                title = u.get("title", "No Title")
                company = u.get("company", "Unknown")
                impact = u.get("impact_level", "medium").upper()
                url = u.get("source_url", "")
                lines.append(f"\n  * {title}")
                lines.append(f"    Company: {company} | Impact: {impact}")
                if url:
                    lines.append(f"    Link: {url}")

        lines.append(f"\n\nGenerated by AI Agent | {date_str}")
        return "\n".join(lines)

    # ── Email sending ────────────────────────────────────────────────────────

    def _send_email(self, subject: str, html_body: str, plain_body: str,
                    pdf_path: str = None) -> bool:
        """Send email with HTML body + optional PDF attachment."""
        if not settings.EMAIL_ENABLED:
            logger.error("Email is disabled in settings")
            return False
        if not settings.EMAIL_SENDER or not settings.EMAIL_PASSWORD or not settings.EMAIL_RECIPIENT:
            logger.error("Email credentials not fully configured (sender/password/recipient)")
            return False

        msg = MIMEMultipart("mixed")
        msg["From"] = settings.EMAIL_SENDER
        msg["To"] = settings.EMAIL_RECIPIENT
        msg["Subject"] = subject

        # Body: alternative (HTML + plain text)
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(plain_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(body_part)

        # Attach PDF if provided
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf_attachment = MIMEBase("application", "octet-stream")
                    pdf_attachment.set_payload(f.read())

                encoders.encode_base64(pdf_attachment)
                pdf_filename = os.path.basename(pdf_path)
                pdf_attachment.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{pdf_filename}"'
                )
                msg.attach(pdf_attachment)
                logger.info("PDF attached: %s", pdf_filename)
            except Exception as e:
                logger.error("Failed to attach PDF: %s", e)

        # Send via SMTP
        try:
            if settings.EMAIL_SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT)
            else:
                server = smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT)
                server.starttls()

            server.login(settings.EMAIL_SENDER, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_SENDER, settings.EMAIL_RECIPIENT, msg.as_string())
            server.quit()
            logger.info("Email sent successfully to %s", settings.EMAIL_RECIPIENT)
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    # ── Public API ───────────────────────────────────────────────────────────

    def send_digest(self, updates: list[dict]) -> bool:
        """Send AI digest via email with HTML body + PDF attachment.

        This is the single entry point for all digest delivery:
        1. Generates a PDF report
        2. Builds a rich HTML email with all updates
        3. Attaches the PDF to the email
        4. Sends everything in one email
        5. Marks all updates as sent in the database
        """
        if not updates:
            logger.warning("No updates to send")
            return True

        date_str = datetime.now(IST).strftime("%d %b %Y")

        # Step 1: Generate PDF
        pdf_path = None
        try:
            from reporting.pdf_generator import generate_pdf_report
            print(f"\n📄 Generating PDF report for {len(updates)} updates...")
            pdf_path = generate_pdf_report(updates)
            if pdf_path and os.path.exists(pdf_path):
                print(f"✅ PDF generated: {pdf_path}")
            else:
                logger.warning("PDF generation returned no path")
        except Exception as e:
            logger.error("PDF generation failed: %s", e, exc_info=True)
            print(f"⚠️ PDF generation failed: {e}")

        # Step 2: Build email content
        html_body = self._build_html_body(updates, date_str)
        plain_body = self._build_plain_body(updates, date_str)
        subject = f"🚀 AI Updates Digest – {date_str} ({len(updates)} updates)"

        # Step 3: Send with retries
        for attempt in range(1, self.max_retries + 1):
            logger.info("Email attempt %d/%d", attempt, self.max_retries)
            print(f"\n📧 Sending email (attempt {attempt}/{self.max_retries})...")

            success = self._send_email(subject, html_body, plain_body, pdf_path)
            if success:
                # Step 4: Mark all as sent
                db = get_db()
                update_ids = [u["id"] for u in updates if "id" in u]
                if update_ids:
                    db.mark_digest_sent(update_ids)
                    logger.info("Marked %d updates as digest_sent", len(update_ids))

                print(f"\n✅ Email sent to {settings.EMAIL_RECIPIENT}")
                print(f"   📊 {len(updates)} updates included")
                if pdf_path:
                    print(f"   📎 PDF attached: {os.path.basename(pdf_path)}")
                return True

            if attempt < self.max_retries:
                logger.info("Retrying in %d seconds...", self.retry_delay)
                time.sleep(self.retry_delay)

        logger.error("Email delivery failed after %d attempts", self.max_retries)
        print(f"\n❌ Failed to send email after {self.max_retries} attempts")
        return False

    def close(self):
        """No persistent resources to close for email notifier."""
        pass
