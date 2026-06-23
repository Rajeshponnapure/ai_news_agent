"""
Feed Configuration Loader — loads base feeds.json + applies health overrides.
Single source of truth for all RSS and Blog feed URLs.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
FEEDS_JSON = BASE_DIR / "feeds.json"
FEEDS_HEALTH_JSON = BASE_DIR / "feeds_health.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return {}


def _save_json(path: Path, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to save %s: %s", path, e)


def load_feeds_config() -> dict[str, list[dict[str, Any]]]:
    """
    Load base feeds.json and apply any health overrides from feeds_health.json.
    Returns dict with 'rss' and 'blog' keys, each a list of feed dicts.
    Only feeds with enabled=True are returned.
    """
    base = _load_json(FEEDS_JSON)
    health = _load_json(FEEDS_HEALTH_JSON)

    overrides = health.get("overrides", {})

    def apply_overrides(feed_list: list[dict], feed_type: str) -> list[dict]:
        result = []
        for feed in feed_list:
            name = feed.get("name", "")
            override = overrides.get(name, {})
            if override.get("disabled"):
                logger.info("Feed disabled by health agent: %s (%s)", name, override.get("reason", "unknown"))
                continue
            url = override.get("url") or feed.get("url")
            enabled = feed.get("enabled", True)
            if not enabled:
                continue
            result.append({**feed, "url": url})
        return result

    return {
        "rss": apply_overrides(base.get("rss", []), "rss"),
        "blog": apply_overrides(base.get("blog", []), "blog"),
    }


def get_rss_feeds() -> dict[str, str]:
    """Return {name: url} for RSS feeds, with health overrides applied."""
    config = load_feeds_config()
    return {f["name"]: f["url"] for f in config["rss"]}


def get_blog_pages() -> dict[str, str]:
    """Return {name: url} for Blog pages, with health overrides applied."""
    config = load_feeds_config()
    return {f["name"]: f["url"] for f in config["blog"]}


def get_blog_scopes() -> dict[str, str]:
    """Return {name: scope} for Blog pages (ai/world)."""
    config = load_feeds_config()
    return {f["name"]: f.get("scope", "ai") for f in config["blog"]}


def get_rss_scopes() -> dict[str, str]:
    """Return {name: scope} for RSS feeds (ai/world)."""
    config = load_feeds_config()
    return {f["name"]: f.get("scope", "ai") for f in config["rss"]}