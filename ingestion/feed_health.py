"""
Feed Health Agent — probes all feeds, auto-repairs broken ones, writes overrides.
Run via: python runner.py feed-health
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from ingestion.feed_config import FEEDS_HEALTH_JSON, load_feeds_config

logger = logging.getLogger(__name__)

COMMON_RSS_PATHS = [
    "/feed/", "/feed.xml", "/rss/", "/rss.xml", "/atom.xml",
    "/index.rss", "/index.xml", "/blog/feed/", "/blog/rss.xml",
    "/news/feed/", "/news/rss.xml", "/rss/feed.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Agent/1.0",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class FeedHealthAgent:
    def __init__(self):
        self.client = httpx.Client(timeout=15.0, follow_redirects=True)
        self.report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checked": 0,
            "healthy": 0,
            "repaired": 0,
            "disabled": 0,
            "errors": [],
            "details": [],
        }

    def _is_valid_feed(self, content: str, content_type: str = "") -> bool:
        """Check if response parses as a valid RSS/Atom feed."""
        if "xml" not in content_type.lower() and "rss" not in content_type.lower():
            if not content.strip().startswith(("<?xml", "<rss", "<feed", "<atom")):
                return False
        try:
            feed = feedparser.parse(content)
            return bool(feed.entries) and not feed.bozo
        except Exception:
            return False

    def _probe_url(self, url: str) -> tuple[bool, str, str]:
        """
        Probe a URL.
        Returns (is_healthy, final_url, error_message)
        """
        try:
            resp = self.client.get(url, headers=HEADERS)
            if resp.status_code >= 400:
                return False, url, f"HTTP {resp.status_code}"
            if self._is_valid_feed(resp.text, resp.headers.get("content-type", "")):
                return True, str(resp.url), ""
            return False, url, "Not a valid RSS/Atom feed"
        except Exception as e:
            return False, url, str(e)

    def _try_repair_rss(self, base_url: str) -> str | None:
        """Try common RSS paths on the same domain."""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in COMMON_RSS_PATHS:
            candidate = urljoin(base + "/", path.lstrip("/"))
            healthy, final_url, _ = self._probe_url(candidate)
            if healthy:
                logger.info("Auto-repaired %s -> %s", base_url, final_url)
                return final_url
        return None

    def _try_repair_blog(self, base_url: str) -> str | None:
        """Try common blog RSS paths for a blog URL."""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        blog_paths = [
            "/feed/", "/feed.xml", "/rss/", "/rss.xml", "/atom.xml",
            "/blog/feed/", "/blog/rss.xml", "/news/feed/",
            "/feed/rss/", "/feed/atom/", "/index.xml",
        ]
        for path in blog_paths:
            candidate = urljoin(base + "/", path.lstrip("/"))
            healthy, final_url, _ = self._probe_url(candidate)
            if healthy:
                logger.info("Auto-repaired blog %s -> %s", base_url, final_url)
                return final_url
        # Try adding https if http
        if base_url.startswith("http://"):
            https_url = base_url.replace("http://", "https://")
            healthy, final_url, _ = self._probe_url(https_url)
            if healthy:
                return final_url
        return None

    def check_feed(self, name: str, url: str, feed_type: str) -> dict[str, Any]:
        """Check a single feed, attempt repair on failure."""
        self.report["checked"] += 1

        healthy, final_url, error = self._probe_url(url)

        if healthy:
            self.report["healthy"] += 1
            result = {
                "name": name,
                "url": url,
                "final_url": final_url,
                "status": "healthy",
                "feed_type": feed_type,
                "repaired": False,
                "error": None,
            }
            self.report["details"].append(result)
            return result

        # Try repair
        repair_url = None
        if feed_type == "rss":
            repair_url = self._try_repair_rss(url)
        else:
            repair_url = self._try_repair_blog(url)

        if repair_url:
            self.report["repaired"] += 1
            result = {
                "name": name,
                "url": url,
                "final_url": repair_url,
                "status": "repaired",
                "feed_type": feed_type,
                "repaired": True,
                "error": error,
            }
            self.report["details"].append(result)
            self._write_override(name, repair_url, feed_type, error, "repaired")
            return result

        # Disable
        self.report["disabled"] += 1
        self.report["errors"].append(f"{name} ({feed_type}): {error}")
        result = {
            "name": name,
            "url": url,
            "final_url": None,
            "status": "disabled",
            "feed_type": feed_type,
            "repaired": False,
            "error": error,
        }
        self.report["details"].append(result)
        self._write_override(name, None, feed_type, error, "disabled")
        return result

    def _write_override(self, name: str, new_url: str | None, feed_type: str, reason: str, kind: str):
        """Write override to feeds_health.json."""
        health = {}
        if FEEDS_HEALTH_JSON.exists():
            try:
                with open(FEEDS_HEALTH_JSON, "r", encoding="utf-8") as f:
                    health = json.load(f)
            except Exception:
                health = {}

        overrides = health.get("overrides", {})

        if kind == "disabled":
            overrides[name] = {
                "disabled": True,
                "reason": reason,
                "kind": feed_type,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        elif new_url:
            overrides[name] = {
                "url": new_url,
                "reason": reason,
                "kind": feed_type,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        health["overrides"] = overrides
        health["generated_at"] = datetime.now(timezone.utc).isoformat()
        health["report"] = {
            "checked": self.report["checked"],
            "healthy": self.report["healthy"],
            "repaired": self.report["repaired"],
            "disabled": self.report["disabled"],
        }

        try:
            with open(FEEDS_HEALTH_JSON, "w", encoding="utf-8") as f:
                json.dump(health, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to write health override for %s: %s", name, e)

    def run(self) -> dict[str, Any]:
        """Check all feeds from feeds.json."""
        config = load_feeds_config()

        # Check RSS feeds
        for feed in config["rss"]:
            self.check_feed(feed["name"], feed["url"], "rss")

        # Check Blog feeds
        for feed in config["blog"]:
            self.check_feed(feed["name"], feed["url"], "blog")

        self.report["checked_at"] = datetime.now(timezone.utc).isoformat()
        return self.report


def run_feed_health_check() -> dict[str, Any]:
    """Entry point for CLI / CI."""
    agent = FeedHealthAgent()
    return agent.run()