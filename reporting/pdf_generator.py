#!/usr/bin/env python3
"""
PDF Report Generator for AI Updates
Creates a professional, well-structured PDF with categorized AI news,
tech launches prioritized, brief explanations, and clean UI.
"""

import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fpdf import FPDF
import requests
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


class PDFReportGenerator:
    """Generates professional PDF reports from AI updates."""
    
    # Category colors for visual distinction
    CATEGORY_COLORS = {
        "FINANCE & BUSINESS": (41, 128, 185),      # Blue
        "MEDICAL & HEALTHCARE": (231, 76, 60),     # Red
        "CODING & DEVELOPMENT": (46, 204, 113),    # Green
        "AI TECH & MODELS": (155, 89, 182),        # Purple
        "INDUSTRIAL & MANUFACTURING": (230, 126, 34),  # Orange
        "AUTONOMOUS & VEHICLES": (52, 152, 219),   # Light Blue
        "RESEARCH & SCIENCE": (26, 188, 156),       # Teal
        "HARDWARE & CHIPS": (241, 196, 15),         # Yellow
        "GENERAL TECH": (149, 165, 166),          # Gray
        "OTHER AI NEWS": (189, 195, 199),          # Light Gray
        "TECH LAUNCHES": (231, 76, 60),             # Red (high priority)
    }
    
    # Emoji mapping for display (PDF uses text, WhatsApp uses emojis)
    CATEGORY_EMOJIS = {
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
        "TECH LAUNCHES": "[TECH LAUNCH]",
    }
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.temp_images = []
        
    def _get_category_for_update(self, update: dict) -> str:
        """Determine category for an update - prioritize tech launches."""
        text = f"{update.get('title', '')} {update.get('summary', '')}".lower()
        company = update.get('company', '').lower()
        
        # First check for tech launches (highest priority)
        launch_keywords = ['launch', 'released', 'announced', 'new', 'introducing', 
                          ' unveiled', ' debuts', 'ships', 'available now', 'beta']
        is_launch = any(kw in text for kw in launch_keywords)
        
        # Check for major tech companies (OpenAI, Google, Anthropic, etc.)
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
    
    def _download_image(self, url: str) -> Optional[str]:
        """Download image and return temp path."""
        if not url or not url.startswith('http'):
            return None
        
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                return None
            
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize to reasonable size
            max_size = (400, 300)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to temp file
            temp_path = tempfile.mktemp(suffix='.jpg')
            img.save(temp_path, 'JPEG', quality=85)
            self.temp_images.append(temp_path)
            
            return temp_path
        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")
            return None
    
    def generate_report(self, updates: list[dict]) -> str:
        """Generate PDF report and return filepath."""
        
        date_str = datetime.now(IST).strftime("%d %b %Y")
        
        # Categorize all updates
        categorized = {}
        for u in updates:
            cat = self._get_category_for_update(u)
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(u)
        
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
        
        # Create PDF with proper margins
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
        
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
        
        # Cleanup temp images
        for img_path in self.temp_images:
            try:
                os.remove(img_path)
            except:
                pass
        self.temp_images = []
        
        logger.info(f"PDF report generated: {filepath}")
        return str(filepath)
    
    def _add_cover_page(self, pdf: FPDF, date_str: str, total_updates: int):
        """Add professional cover page."""
        # Reset margins for cover
        pdf.set_left_margin(0)
        pdf.set_right_margin(0)
        
        # Background color (light gray)
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(0, 0, 210, 297, 'F')
        
        # Title
        pdf.set_font("Helvetica", "B", 36)
        pdf.set_text_color(44, 62, 80)
        pdf.ln(60)
        pdf.cell(210, 20, "AI UPDATE DIGEST", ln=True, align='C')
        
        # Subtitle
        pdf.set_font("Helvetica", "", 18)
        pdf.set_text_color(127, 140, 141)
        pdf.cell(210, 15, "Daily Intelligence Briefing", ln=True, align='C')
        
        # Date
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(41, 128, 185)
        pdf.ln(20)
        pdf.cell(210, 15, date_str, ln=True, align='C')
        
        # Stats box
        pdf.ln(30)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(41, 128, 185)
        pdf.rect(55, 160, 100, 40, style='DF')
        
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(127, 140, 141)
        pdf.set_xy(55, 170)
        pdf.cell(100, 10, "Total Updates Analyzed", ln=True, align='C')
        
        pdf.set_font("Helvetica", "B", 32)
        pdf.set_text_color(41, 128, 185)
        pdf.set_xy(55, 182)
        pdf.cell(100, 10, str(total_updates), ln=True, align='C')
        
        # Footer
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(149, 165, 166)
        pdf.set_y(270)
        pdf.cell(210, 10, "Generated by AI Agent | Sources: NewsAPI, GitHub, RSS, Tech Blogs", 
                 ln=True, align='C')
        
        # Reset margins for content pages
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
    
    def _add_table_of_contents(self, pdf: FPDF, categorized: dict, priority_order: list):
        """Add table of contents."""
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(180, 15, "Table of Contents", ln=True, align='L')
        pdf.ln(10)
        
        pdf.set_draw_color(189, 195, 199)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(15)
        
        for cat in priority_order:
            if cat not in categorized or not categorized[cat]:
                continue
            
            count = len(categorized[cat])
            color = self.CATEGORY_COLORS.get(cat, (149, 165, 166))
            display_name = self.CATEGORY_EMOJIS.get(cat, cat)
            
            # Category color indicator
            pdf.set_fill_color(*color)
            pdf.rect(10, pdf.get_y() + 2, 5, 8, 'F')
            
            # Category name and count
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(44, 62, 80)
            pdf.set_x(20)
            pdf.cell(140, 12, f"{display_name} {cat}", ln=0)
            
            pdf.set_font("Helvetica", "", 12)
            pdf.set_text_color(127, 140, 141)
            pdf.cell(30, 12, f"({count} items)", ln=True, align='R')
            
            pdf.ln(5)
    
    def _add_category_section(self, pdf: FPDF, category: str, updates: list):
        """Add a category section with all updates."""
        color = self.CATEGORY_COLORS.get(category, (149, 165, 166))
        display_name = self.CATEGORY_EMOJIS.get(category, category)
        
        # Category header with colored background
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(180, 12, f"  {display_name} {category}", ln=True, fill=True)
        pdf.ln(3)
        
        # Sort updates: High impact first, then by recency
        impact_order = {"high": 0, "medium": 1, "low": 2}
        updates.sort(key=lambda u: (impact_order.get(u.get("impact_level", "low"), 2)))
        
        for update in updates:
            self._add_update_entry(pdf, update, color)
            pdf.ln(8)
    
    def _add_update_entry(self, pdf: FPDF, update: dict, category_color: tuple):
        """Add a single update entry."""
        title = update.get('title', 'No Title')[:100]
        company = update.get('company', 'Unknown')
        summary = update.get('summary', '')[:250]
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
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(25, 8, f" {impact}", ln=0, fill=True)
        
        # Company name
        pdf.set_text_color(127, 140, 141)
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, f"  {company}", ln=True)
        
        # Title
        pdf.set_text_color(44, 62, 80)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(170, 6, title)
        
        # Summary
        if summary:
            pdf.set_text_color(100, 100, 100)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(170, 5, summary)
        
        # URL
        if url:
            pdf.set_text_color(41, 128, 185)
            pdf.set_font("Helvetica", "U", 8)
            url_text = url[:70] + "..." if len(url) > 70 else url
            pdf.cell(170, 5, f"Read more: {url_text}", ln=True, link=url)
        
        # Separator line
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())


def generate_pdf_report(updates: list[dict], output_dir: str = "reports") -> str:
    """Convenience function to generate PDF report."""
    generator = PDFReportGenerator(output_dir)
    return generator.generate_report(updates)
