#!/usr/bin/env python3
"""
PDF Report Generator for AI Updates
Creates a professional, well-structured PDF with categorized AI news,
tech launches prioritized, brief explanations, and clean UI.

Uses DejaVu font for full Unicode support (Bug 14 fix).
"""

import logging
import os
import tempfile
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Path to system Unicode fonts
_FONT_PATHS = None


def _find_unicode_fonts() -> dict:
    """Find Unicode TTF fonts on the system (Windows, Linux, macOS).
    
    Returns a dict with keys '', 'B', 'I' mapping to font file paths.
    Uses Arial on Windows (always available), falls back to DejaVu on Linux.
    """
    global _FONT_PATHS
    if _FONT_PATHS is not None:
        return _FONT_PATHS

    _FONT_PATHS = {}
    
    # Windows system fonts
    win_fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    if os.path.isdir(win_fonts_dir):
        # Try Arial first (most reliable Unicode font on Windows)
        arial_map = {
            "": "arial.ttf",
            "B": "arialbd.ttf",
            "I": "ariali.ttf",
        }
        all_found = True
        for style, filename in arial_map.items():
            path = os.path.join(win_fonts_dir, filename)
            if os.path.exists(path):
                _FONT_PATHS[style] = path
            else:
                all_found = False
        if all_found:
            logger.info("Using Windows Arial font for Unicode support")
            return _FONT_PATHS
        _FONT_PATHS = {}  # Reset if not all styles found
    
    # Linux: try DejaVu
    for fonts_dir in ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu"]:
        if os.path.isdir(fonts_dir):
            dejavu_map = {
                "": "DejaVuSans.ttf",
                "B": "DejaVuSans-Bold.ttf",
                "I": "DejaVuSans-Oblique.ttf",
            }
            for style, filename in dejavu_map.items():
                path = os.path.join(fonts_dir, filename)
                if os.path.exists(path):
                    _FONT_PATHS[style] = path
            if _FONT_PATHS:
                logger.info("Using DejaVu font for Unicode support")
                return _FONT_PATHS
    
    # fpdf2 bundled fonts
    import fpdf
    fpdf_font_dir = Path(fpdf.__file__).parent / "fonts"
    if fpdf_font_dir.is_dir():
        for ttf in fpdf_font_dir.glob("*.ttf"):
            if "bold" in ttf.stem.lower():
                _FONT_PATHS.setdefault("B", str(ttf))
            elif "oblique" in ttf.stem.lower() or "italic" in ttf.stem.lower():
                _FONT_PATHS.setdefault("I", str(ttf))
            else:
                _FONT_PATHS.setdefault("", str(ttf))
    
    if not _FONT_PATHS:
        logger.warning("No Unicode TTF fonts found — PDF will use Helvetica (latin-1 only)")
    
    return _FONT_PATHS


def _sanitize_text(text: str) -> str:
    """Sanitize text for PDF output — remove/replace problematic characters.
    
    BUG-14 FIX: Even with Unicode fonts, some control characters or unusual
    Unicode categories can cause issues. This strips them.
    """
    if not text:
        return ""
    # Replace common problematic characters
    replacements = {
        '\u200b': '',       # Zero-width space
        '\u200c': '',       # Zero-width non-joiner
        '\u200d': '',       # Zero-width joiner
        '\ufeff': '',       # BOM
        '\u00a0': ' ',      # Non-breaking space → regular space
        '\r\n': '\n',       # Windows newline
        '\r': '\n',         # Old Mac newline
        '\t': '    ',       # Tab → spaces
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove control characters (except newline)
    text = ''.join(
        c for c in text
        if c == '\n' or unicodedata.category(c)[0] != 'C'
    )
    return text.strip()


class PDFReportGenerator:
    """Generates professional PDF reports from AI updates."""
    
    # Category colors for visual distinction
    CATEGORY_COLORS = {
        "FINANCE & BUSINESS": (41, 128, 185),
        "MEDICAL & HEALTHCARE": (231, 76, 60),
        "CODING & DEVELOPMENT": (46, 204, 113),
        "AI TECH & MODELS": (155, 89, 182),
        "INDUSTRIAL & MANUFACTURING": (230, 126, 34),
        "AUTONOMOUS & VEHICLES": (52, 152, 219),
        "RESEARCH & SCIENCE": (26, 188, 156),
        "HARDWARE & CHIPS": (241, 196, 15),
        "GENERAL TECH": (149, 165, 166),
        "OTHER AI NEWS": (189, 195, 199),
        "TECH LAUNCHES": (231, 76, 60),
    }
    
    CATEGORY_LABELS = {
        "FINANCE & BUSINESS": "[FINANCE]",
        "MEDICAL & HEALTHCARE": "[MEDICAL]",
        "CODING & DEVELOPMENT": "[CODING]",
        "AI TECH & MODELS": "[AI TECH]",
        "INDUSTRIAL & MANUFACTURING": "[INDUSTRIAL]",
        "AUTONOMOUS & VEHICLES": "[AUTONOMOUS]",
        "RESEARCH & SCIENCE": "[RESEARCH]",
        "HARDWARE & CHIPS": "[HARDWARE]",
        "GENERAL TECH": "[TECH]",
        "OTHER AI NEWS": "[OTHER]",
        "TECH LAUNCHES": "[LAUNCH]",
    }
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self._font_registered = False
        
    def _get_category_for_update(self, update: dict) -> str:
        """Determine category for an update - prioritize tech launches."""
        text = f"{update.get('title', '')} {update.get('summary', '')}".lower()
        company = update.get('company', '').lower()
        
        # First check for tech launches (highest priority)
        launch_keywords = ['launch', 'released', 'announced', 'new', 'introducing', 
                          ' unveiled', ' debuts', 'ships', 'available now', 'beta']
        is_launch = any(kw in text for kw in launch_keywords)
        
        # Check for major tech companies
        major_tech = ['openai', 'anthropic', 'google', 'deepmind', 'meta', 'microsoft',
                      'nvidia', 'amazon', 'apple', 'tesla']
        is_major_tech = any(tech in company for tech in major_tech)
        
        if is_launch and is_major_tech:
            return "TECH LAUNCHES"
        
        # Otherwise use standard categorization
        categories = {
            "FINANCE & BUSINESS": [
                "finance", "banking", "fintech", "trading", "investment", "stock",
                "economy", "market", "revenue", "profit", "ipo", "acquisition",
                "valuation", "funding", "enterprise", "business"
            ],
            "MEDICAL & HEALTHCARE": [
                "healthcare", "medical", "health", "drug", "diagnosis", "clinical",
                "pharma", "biotech", "biology", "therapy", "treatment", "medicine"
            ],
            "CODING & DEVELOPMENT": [
                "coding", "programming", "developer", "devops", "software",
                "github", "code", "api", "sdk", "framework", "library"
            ],
            "AI TECH & MODELS": [
                "gpt", "claude", "gemini", "llama", "mistral", "model", "llm",
                "transformer", "neural", "deep learning", "machine learning",
                "benchmark", "training", "inference", "multimodal", "diffusion"
            ],
            "HARDWARE & CHIPS": [
                "nvidia", "gpu", "tpu", "chip", "hardware", "cuda", "semiconductor",
                "processor", "cpu", "h100", "h200", "blackwell", "data center"
            ],
            "INDUSTRIAL & MANUFACTURING": [
                "manufacturing", "factory", "robotics", "automation", "industrial",
                "supply chain", "logistics", "iot"
            ],
            "AUTONOMOUS & VEHICLES": [
                "autonomous", "self-driving", "vehicle", "waymo", "drone"
            ],
            "RESEARCH & SCIENCE": [
                "research", "paper", "arxiv", "publication", "academic",
                "scientific", "breakthrough", "quantum"
            ],
        }
        
        scores = {}
        for cat, keywords in categories.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[cat] = score
        
        if not scores:
            return "GENERAL TECH" if "tech" in text else "OTHER AI NEWS"
        
        return max(scores, key=scores.get)
    
    def _setup_pdf(self) -> FPDF:
        """Create PDF instance with Unicode font support.
        
        BUG-14 FIX: Register system Unicode font (Arial on Windows, DejaVu on Linux)
        to prevent UnicodeEncodeError crashes and missing characters.
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=25)
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
        
        # Find and register Unicode font
        font_paths = _find_unicode_fonts()
        if font_paths:
            try:
                font_name = "UniFont"
                for style, path in font_paths.items():
                    pdf.add_font(font_name, style, path)
                self._font_registered = True
                logger.info("Unicode font registered with %d styles", len(font_paths))
            except Exception as e:
                logger.warning("Failed to register Unicode font: %s — falling back to Helvetica", e)
                self._font_registered = False
        
        return pdf
    
    def _font(self, style: str = "") -> str:
        """Return the font name to use (UniFont if available, else Helvetica)."""
        return "UniFont" if self._font_registered else "Helvetica"
    
    def generate_report(self, updates: list[dict]) -> str:
        """Generate PDF report and return filepath."""
        
        date_str = datetime.now(IST).strftime("%d %b %Y")
        
        # Categorize all updates
        categorized = {}
        for u in updates:
            cat = self._get_category_for_update(u)
            categorized.setdefault(cat, []).append(u)
        
        # Sort categories: Tech Launches first, then by priority
        priority_order = [
            "TECH LAUNCHES",
            "HARDWARE & CHIPS",
            "AI TECH & MODELS",
            "CODING & DEVELOPMENT",
            "FINANCE & BUSINESS",
            "MEDICAL & HEALTHCARE",
            "RESEARCH & SCIENCE",
            "INDUSTRIAL & MANUFACTURING",
            "AUTONOMOUS & VEHICLES",
            "GENERAL TECH",
            "OTHER AI NEWS"
        ]
        
        # Create PDF with Unicode support (BUG-14 FIX)
        pdf = self._setup_pdf()
        
        # Cover page
        pdf.add_page()
        self._add_cover_page(pdf, date_str, len(updates))
        
        # Table of contents
        pdf.add_page()
        self._add_table_of_contents(pdf, categorized, priority_order)
        
        # Category pages
        for cat in priority_order:
            if cat not in categorized or not categorized[cat]:
                continue
            
            pdf.add_page()
            self._add_category_section(pdf, cat, categorized[cat])
        
        # Save PDF
        filename = f"AI_Digest_{datetime.now(IST).strftime('%Y%m%d')}.pdf"
        filepath = self.output_dir / filename
        pdf.output(str(filepath))
        
        logger.info("PDF report generated: %s", filepath)
        return str(filepath)
    
    def _add_cover_page(self, pdf: FPDF, date_str: str, total_updates: int):
        """Add professional cover page.
        
        BUG-18 FIX: Use consistent margin handling and proper cell widths.
        """
        font = self._font()
        
        # Save current margins
        left_margin = pdf.l_margin
        right_margin = pdf.r_margin
        page_width = pdf.w  # 210mm for A4
        
        # Background color
        pdf.set_fill_color(245, 245, 245)
        pdf.set_left_margin(0)
        pdf.set_right_margin(0)
        pdf.rect(0, 0, page_width, 297, 'F')
        
        # Title
        pdf.set_font(font, "B", 36)
        pdf.set_text_color(44, 62, 80)
        pdf.ln(60)
        pdf.cell(page_width, 20, _sanitize_text("AI UPDATE DIGEST"), ln=True, align='C')
        
        # Subtitle
        pdf.set_font(font, "", 18)
        pdf.set_text_color(127, 140, 141)
        pdf.cell(page_width, 15, _sanitize_text("Daily Intelligence Briefing"), ln=True, align='C')
        
        # Date
        pdf.set_font(font, "B", 24)
        pdf.set_text_color(41, 128, 185)
        pdf.ln(20)
        pdf.cell(page_width, 15, _sanitize_text(date_str), ln=True, align='C')
        
        # Stats box
        pdf.ln(30)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(41, 128, 185)
        box_x = (page_width - 100) / 2
        pdf.rect(box_x, 160, 100, 40, style='DF')
        
        pdf.set_font(font, "", 12)
        pdf.set_text_color(127, 140, 141)
        pdf.set_xy(box_x, 170)
        pdf.cell(100, 10, _sanitize_text("Total Updates Analyzed"), ln=True, align='C')
        
        pdf.set_font(font, "B", 32)
        pdf.set_text_color(41, 128, 185)
        pdf.set_xy(box_x, 182)
        pdf.cell(100, 10, str(total_updates), ln=True, align='C')
        
        # Footer
        pdf.set_font(font, "I" if not self._font_registered else "", 10)
        pdf.set_text_color(149, 165, 166)
        pdf.set_y(270)
        pdf.cell(page_width, 10, _sanitize_text("Generated by AI Agent | Sources: NewsAPI, GitHub, RSS, Tech Blogs"), 
                 ln=True, align='C')
        
        # Restore margins for content pages (BUG-18 FIX)
        pdf.set_left_margin(left_margin)
        pdf.set_right_margin(right_margin)
    
    def _add_table_of_contents(self, pdf: FPDF, categorized: dict, priority_order: list):
        """Add table of contents."""
        font = self._font()
        content_width = pdf.w - pdf.l_margin - pdf.r_margin  # Dynamic width
        
        pdf.set_font(font, "B", 24)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(content_width, 15, _sanitize_text("Table of Contents"), ln=True, align='L')
        pdf.ln(10)
        
        pdf.set_draw_color(189, 195, 199)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(15)
        
        for cat in priority_order:
            if cat not in categorized or not categorized[cat]:
                continue
            
            count = len(categorized[cat])
            color = self.CATEGORY_COLORS.get(cat, (149, 165, 166))
            display_name = self.CATEGORY_LABELS.get(cat, cat)
            
            # Category color indicator
            pdf.set_fill_color(*color)
            pdf.rect(pdf.l_margin, pdf.get_y() + 2, 5, 8, 'F')
            
            # Category name and count
            pdf.set_font(font, "B", 14)
            pdf.set_text_color(44, 62, 80)
            pdf.set_x(pdf.l_margin + 10)
            pdf.cell(content_width - 40, 12, _sanitize_text(f"{display_name} {cat}"), ln=0)
            
            pdf.set_font(font, "", 12)
            pdf.set_text_color(127, 140, 141)
            pdf.cell(30, 12, f"({count} items)", ln=True, align='R')
            
            pdf.ln(5)
    
    def _add_category_section(self, pdf: FPDF, category: str, updates: list):
        """Add a category section with all updates.
        
        BUG-16 FIX: Check remaining page space before drawing each entry.
        """
        font = self._font()
        color = self.CATEGORY_COLORS.get(category, (149, 165, 166))
        display_name = self.CATEGORY_LABELS.get(category, category)
        content_width = pdf.w - pdf.l_margin - pdf.r_margin
        
        # Category header with colored background
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font, "B", 16)
        pdf.cell(content_width, 12, _sanitize_text(f"  {display_name} {category}"), ln=True, fill=True)
        pdf.ln(3)
        
        # Sort updates: High impact first, then by recency
        impact_order = {"high": 0, "medium": 1, "low": 2}
        updates.sort(key=lambda u: (impact_order.get(u.get("impact_level", "low"), 2)))
        
        for update in updates:
            # BUG-16 FIX: Check if enough space for an entry (~60mm minimum)
            if pdf.get_y() > pdf.h - 65:
                pdf.add_page()
                # Re-draw category header on continuation page
                pdf.set_fill_color(*color)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font(font, "B", 12)
                pdf.cell(content_width, 10, _sanitize_text(f"  {display_name} {category} (continued)"), ln=True, fill=True)
                pdf.ln(3)
            
            self._add_update_entry(pdf, update, color, content_width)
            pdf.ln(5)
    
    def _add_update_entry(self, pdf: FPDF, update: dict, category_color: tuple, content_width: float):
        """Add a single update entry.
        
        BUG-14 FIX: All text is sanitized before rendering.
        BUG-15 FIX: Show full summary (up to 500 chars, not truncated to 250).
        BUG-16 FIX: Separator line drawn relative to current position.
        """
        font = self._font()
        title = _sanitize_text(update.get('title', 'No Title'))[:150]
        company = _sanitize_text(update.get('company', 'Unknown'))
        summary = _sanitize_text(update.get('summary', ''))[:500]  # BUG-15 FIX: full 500 chars
        impact = update.get('impact_level', 'medium').upper()
        url = update.get('source_url', '')
        
        # Impact badge
        impact_colors = {
            "HIGH": (231, 76, 60),
            "MEDIUM": (241, 196, 15),
            "LOW": (149, 165, 166)
        }
        badge_color = impact_colors.get(impact, (149, 165, 166))
        
        pdf.set_fill_color(*badge_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font, "B", 10)
        pdf.cell(25, 8, f" {impact}", ln=0, fill=True)
        
        # Company name
        pdf.set_text_color(127, 140, 141)
        pdf.set_font(font, "I" if not self._font_registered else "", 10)
        pdf.cell(0, 8, f"  {company}", ln=True)
        
        # Title
        pdf.set_text_color(44, 62, 80)
        pdf.set_font(font, "B", 12)
        pdf.multi_cell(content_width, 6, title)
        
        # Summary — only show if different from title (BUG-2 residual fix)
        if summary and summary.strip().lower() != title.strip().lower():
            pdf.set_text_color(100, 100, 100)
            pdf.set_font(font, "", 10)
            pdf.multi_cell(content_width, 5, summary)
        
        # URL
        if url:
            pdf.set_text_color(41, 128, 185)
            pdf.set_font(font, "" if self._font_registered else "U", 8)
            url_text = url[:80] + "..." if len(url) > 80 else url
            pdf.cell(content_width, 5, _sanitize_text(f"Read more: {url_text}"), ln=True, link=url)
        
        # BUG-16 FIX: Separator line at current Y position (not hardcoded)
        y_pos = pdf.get_y() + 2
        if y_pos < pdf.h - pdf.b_margin:  # Only draw if still on page
            pdf.set_draw_color(220, 220, 220)
            pdf.line(pdf.l_margin, y_pos, pdf.w - pdf.r_margin, y_pos)
            pdf.ln(3)


def generate_pdf_report(updates: list[dict], output_dir: str = "reports") -> str:
    """Convenience function to generate PDF report."""
    generator = PDFReportGenerator(output_dir)
    return generator.generate_report(updates)
