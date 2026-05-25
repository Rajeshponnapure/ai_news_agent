#!/usr/bin/env python3
import logging
import os
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_FONT_PATHS = None

# Map pipeline emoji categories to clean PDF labels and colors
CATEGORY_MAP = {
    "🚀 AI LAUNCHES & RELEASES": {
        "label": "AI LAUNCHES & RELEASES",
        "color": (231, 76, 60),
        "icon": "🚀",
    },
    "💰 FINANCE & FINTECH AI": {
        "label": "FINANCE & FINTECH AI",
        "color": (52, 152, 219),
        "icon": "💰",
    },
    "📣 MARKETING & GROWTH AI": {
        "label": "MARKETING & GROWTH AI",
        "color": (142, 68, 173),
        "icon": "📣",
    },
    "💻 AI CODING & DEVELOPER TOOLS": {
        "label": "AI CODING & DEVELOPER TOOLS",
        "color": (39, 174, 96),
        "icon": "💻",
    },
    "⚡ HARDWARE & INFRASTRUCTURE": {
        "label": "HARDWARE & INFRASTRUCTURE",
        "color": (230, 126, 34),
        "icon": "⚡",
    },
    "🏥 MEDICAL & HEALTHCARE AI": {
        "label": "MEDICAL & HEALTHCARE AI",
        "color": (26, 188, 156),
        "icon": "🏥",
    },
    "🤖 ROBOTICS & AUTOMATION": {
        "label": "ROBOTICS & AUTOMATION",
        "color": (230, 126, 34),
        "icon": "🤖",
    },
    "⚠️ AI SAFETY & ETHICS": {
        "label": "AI SAFETY & ETHICS",
        "color": (231, 76, 60),
        "icon": "⚠️",
    },
    "🔬 RESEARCH & SCIENCE": {
        "label": "RESEARCH & SCIENCE",
        "color": (22, 160, 133),
        "icon": "🔬",
    },
    "📰 OTHER AI NEWS": {
        "label": "OTHER AI NEWS",
        "color": (127, 140, 141),
        "icon": "📰",
    },
}

CATEGORY_ORDER = [
    "🚀 AI LAUNCHES & RELEASES",
    "💰 FINANCE & FINTECH AI",
    "📣 MARKETING & GROWTH AI",
    "💻 AI CODING & DEVELOPER TOOLS",
    "⚡ HARDWARE & INFRASTRUCTURE",
    "🏥 MEDICAL & HEALTHCARE AI",
    "🤖 ROBOTICS & AUTOMATION",
    "⚠️ AI SAFETY & ETHICS",
    "🔬 RESEARCH & SCIENCE",
    "📰 OTHER AI NEWS",
]


def _find_unicode_fonts() -> dict:
    global _FONT_PATHS
    if _FONT_PATHS is not None:
        return _FONT_PATHS

    _FONT_PATHS = {}

    win_fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    if os.path.isdir(win_fonts_dir):
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
        _FONT_PATHS = {}

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
    if not text:
        return ""
    replacements = {
        '\u200b': '',
        '\u200c': '',
        '\u200d': '',
        '\ufeff': '',
        '\u00a0': ' ',
        '\r\n': '\n',
        '\r': '\n',
        '\t': '    ',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = ''.join(
        c for c in text
        if c == '\n' or unicodedata.category(c)[0] != 'C'
    )
    return text.strip()


class PDFReportGenerator:

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self._font_registered = False
        self._used_categories = []

    def _setup_pdf(self) -> FPDF:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=25)
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)

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
        return "UniFont" if self._font_registered else "Helvetica"

    def generate_report(self, updates: list[dict]) -> str:
        date_str = datetime.now(IST).strftime("%d %b %Y")

        categorized = {}
        for u in updates:
            raw_cat = u.get("category", "📰 OTHER AI NEWS")
            if raw_cat not in CATEGORY_MAP:
                raw_cat = "📰 OTHER AI NEWS"
            categorized.setdefault(raw_cat, []).append(u)

        self._used_categories = [c for c in CATEGORY_ORDER if c in categorized]

        launches = sum(1 for u in updates if u.get("is_launch"))
        companies = len(set(u.get("company", "") for u in updates if u.get("company")))

        pdf = self._setup_pdf()

        self._add_cover_page(pdf, date_str, len(updates), launches, companies)

        pdf.add_page()
        self._add_table_of_contents(pdf, categorized)

        for cat in self._used_categories:
            pdf.add_page()
            self._add_category_section(pdf, cat, categorized[cat])

        filename = f"AI_Digest_{datetime.now(IST).strftime('%Y%m%d')}.pdf"
        filepath = self.output_dir / filename
        pdf.output(str(filepath))

        logger.info("PDF report generated: %s", filepath)
        print(f"   PDF generated: {filepath.name}")
        return str(filepath)

    def _add_cover_page(self, pdf: FPDF, date_str: str, total: int, launches: int, companies: int):
        pdf.add_page()
        font = self._font()
        pw = pdf.w

        pdf.set_fill_color(20, 26, 46)
        pdf.rect(0, 0, pw, 297, 'F')

        accent_color = (41, 128, 185)

        pdf.ln(50)

        pdf.set_font(font, "B", 44)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(pw, 22, "AI UPDATE DIGEST", ln=True, align='C')

        pdf.set_font(font, "", 20)
        pdf.set_text_color(*accent_color)
        pdf.cell(pw, 14, "Daily Intelligence Briefing", ln=True, align='C')

        pdf.set_font(font, "", 14)
        pdf.set_text_color(180, 190, 200)
        pdf.cell(pw, 12, date_str, ln=True, align='C')

        pdf.ln(25)

        card_y = pdf.get_y()
        card_w = 140
        card_h = 55
        card_x = (pw - card_w) / 2

        pdf.set_fill_color(30, 40, 65)
        pdf.set_draw_color(*accent_color)
        pdf.rect(card_x, card_y, card_w, card_h, style='DF')

        pdf.set_font(font, "", 11)
        pdf.set_text_color(160, 170, 185)
        pdf.set_xy(card_x, card_y + 8)
        pdf.cell(card_w, 8, "TOTAL UPDATES", ln=True, align='C')

        pdf.set_font(font, "B", 36)
        pdf.set_text_color(*accent_color)
        pdf.set_xy(card_x, card_y + 18)
        pdf.cell(card_w, 14, str(total), ln=True, align='C')

        pdf.set_font(font, "", 11)
        pdf.set_text_color(160, 170, 185)
        pdf.set_xy(card_x, card_y + 34)
        pdf.cell(card_w, 8, f"{launches} LAUNCHES  |  {companies} SOURCES", ln=True, align='C')

        pdf.set_font(font, "", 9)
        pdf.set_text_color(100, 110, 130)
        pdf.set_y(270)
        pdf.cell(pw, 10, "Generated by AI News Agent  |  Sources: NewsAPI, GitHub Releases, RSS Feeds, Tech Blogs",
                 ln=True, align='C')

    def _add_table_of_contents(self, pdf: FPDF, categorized: dict):
        font = self._font()
        pw = pdf.w
        lm = pdf.l_margin
        cw = pw - lm - pdf.r_margin

        pdf.set_fill_color(20, 26, 46)
        pdf.rect(0, 0, pw, 297, 'F')

        pdf.set_font(font, "B", 26)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(cw, 18, "TABLE OF CONTENTS", ln=True)
        pdf.ln(6)

        pdf.set_draw_color(41, 128, 185)
        y = pdf.get_y()
        pdf.line(lm, y, pw - pdf.r_margin, y)
        pdf.ln(10)

        for cat in self._used_categories:
            info = CATEGORY_MAP.get(cat, {"label": cat, "color": (127, 140, 141), "icon": "📰"})
            count = len(categorized[cat])
            color = info["color"]

            pdf.set_fill_color(*color)
            pdf.rect(lm, pdf.get_y() + 2, 6, 10, 'F')

            pdf.set_font(font, "B", 14)
            pdf.set_text_color(220, 225, 235)
            pdf.set_x(lm + 12)
            pdf.cell(cw - 50, 14, f"{info['icon']}  {info['label']}", ln=0)

            pdf.set_font(font, "", 12)
            pdf.set_text_color(120, 130, 150)
            pdf.cell(30, 14, f"{count} items", ln=True, align='R')
            pdf.ln(3)

        pdf.ln(20)

        total = sum(len(v) for v in categorized.values())
        pdf.set_font(font, "", 10)
        pdf.set_text_color(100, 110, 130)
        pdf.cell(cw, 8, f"Total: {total} updates across {len(self._used_categories)} categories",
                 ln=True, align='C')

    def _add_category_section(self, pdf: FPDF, category: str, updates: list):
        font = self._font()
        info = CATEGORY_MAP.get(category, {"label": category, "color": (127, 140, 141), "icon": "📰"})
        color = info["color"]
        cw = pdf.w - pdf.l_margin - pdf.r_margin

        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font, "B", 18)
        pdf.cell(cw, 14, f"  {info['icon']}  {info['label']}", ln=True, fill=True)
        pdf.ln(4)

        impact_order = {"high": 0, "medium": 1, "low": 2}
        updates_sorted = sorted(
            updates,
            key=lambda u: (
                impact_order.get(u.get("impact_level", "low"), 2),
                not u.get("is_launch", False),
                u.get("timestamp", ""),
            )
        )

        for i, update in enumerate(updates_sorted):
            if pdf.get_y() > pdf.h - 55:
                pdf.add_page()
                pdf.set_fill_color(*color)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font(font, "B", 14)
                pdf.cell(cw, 10, f"  {info['icon']}  {info['label']} (continued)", ln=True, fill=True)
                pdf.ln(4)

            self._add_update_entry(pdf, update, color, cw, i + 1)

    def _add_update_entry(self, pdf: FPDF, update: dict, cat_color: tuple, cw: float, index: int):
        font = self._font()
        title = _sanitize_text(update.get('title', 'No Title'))[:200]
        company = _sanitize_text(update.get('company', 'Unknown'))
        summary = _sanitize_text(update.get('summary', ''))
        impact = update.get('impact_level', 'medium').upper()
        url = update.get('source_url', '')
        is_launch = update.get('is_launch', False)

        impact_colors = {
            "HIGH": (200, 50, 40),
            "MEDIUM": (220, 170, 20),
            "LOW": (140, 150, 155),
        }
        badge_color = impact_colors.get(impact, (140, 150, 155))

        left_bar_x = pdf.l_margin
        content_x = pdf.l_margin + 3
        content_w = cw - 3

        pdf.set_draw_color(*cat_color)
        pdf.line(left_bar_x, pdf.get_y(), left_bar_x, pdf.get_y() + 40)

        pdf.set_x(content_x)
        pdf.set_fill_color(*badge_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(font, "B", 9)
        badge_w = pdf.get_string_width(f" {impact} ") + 3
        pdf.cell(badge_w, 7, f" {impact} ", ln=0, fill=True)

        launch_text = ""
        if is_launch:
            pdf.set_text_color(200, 50, 40)
            pdf.set_font(font, "B", 9)
            pdf.cell(3, 7, "", ln=0)
            pdf.cell(18, 7, " LAUNCH", ln=0)

        pdf.set_text_color(120, 130, 150)
        pdf.set_font(font, "I" if not self._font_registered else "", 9)
        pdf.cell(3, 7, "", ln=0)
        company_display = company[:40] if len(company) > 40 else company
        pdf.cell(cw - badge_w - 30, 7, f"  {company_display}", ln=True)

        pdf.set_x(content_x)
        pdf.set_text_color(40, 50, 65)
        pdf.set_font(font, "B", 11)
        pdf.multi_cell(content_w, 5.5, title)
        pdf.ln(0.5)

        if summary and summary.strip().lower() not in title.strip().lower():
            pdf.set_x(content_x)
            pdf.set_text_color(90, 95, 105)
            pdf.set_font(font, "", 9)
            summary_clean = summary[:400]
            pdf.multi_cell(content_w, 4.5, summary_clean)
            pdf.ln(0.5)

        if url:
            pdf.set_x(content_x)
            pdf.set_text_color(41, 100, 180)
            pdf.set_font(font, "" if self._font_registered else "U", 8)
            url_text = url[:90] + "..." if len(url) > 90 else url
            pdf.cell(content_w, 5, _sanitize_text(f"Read more: {url_text}"), ln=True, link=url)

        y_after = pdf.get_y() + 2
        if y_after < pdf.h - pdf.b_margin:
            pdf.set_draw_color(215, 220, 225)
            pdf.line(pdf.l_margin, y_after, pdf.w - pdf.r_margin, y_after)
            pdf.ln(4)


def generate_pdf_report(updates: list[dict], output_dir: str = "reports") -> str:
    generator = PDFReportGenerator(output_dir)
    return generator.generate_report(updates)
