import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS updates (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    summary TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    impact_level TEXT NOT NULL CHECK(impact_level IN ('high', 'medium', 'low')),
    source_url TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    digest_sent INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_updates_timestamp ON updates(timestamp);
CREATE INDEX IF NOT EXISTS idx_updates_company ON updates(company);
CREATE INDEX IF NOT EXISTS idx_updates_impact ON updates(impact_level);
CREATE INDEX IF NOT EXISTS idx_updates_digest_sent ON updates(digest_sent);
CREATE INDEX IF NOT EXISTS idx_updates_title_company ON updates(title, company);
"""


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.SQLITE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self):
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def insert_update(
        self,
        title: str,
        company: str,
        summary: str,
        timestamp: str,
        impact_level: str,
        source_url: str,
        source_name: str = "",
    ) -> str:
        entry_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO updates
                    (id, title, company, summary, timestamp, impact_level, source_url, source_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, title, company, summary, timestamp, impact_level, source_url, source_name),
            )
            conn.commit()
            return entry_id
        finally:
            conn.close()

    def get_last_24h(self) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM updates
                WHERE timestamp >= ? AND digest_sent = 0
                ORDER BY
                    CASE impact_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    timestamp DESC
                """,
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_top_updates(self, limit: int = 10) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM updates
                WHERE timestamp >= ? AND digest_sent = 0
                ORDER BY
                    CASE impact_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    timestamp DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_digest_sent(self, update_ids: list[str]):
        if not update_ids:
            return
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" for _ in update_ids)
            conn.execute(
                f"UPDATE updates SET digest_sent = 1 WHERE id IN ({placeholders})",
                update_ids,
            )
            conn.commit()
        finally:
            conn.close()

    def title_exists(self, title: str, company: str, hours: int = 48) -> bool:
        """Check if title exists within the last N hours (default 48h).
        This allows fresh daily data to flow while preventing immediate duplicates."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM updates WHERE title = ? AND company = ? AND timestamp >= ? LIMIT 1",
                (title, company, cutoff),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def cleanup_old(self, days: int = 3):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM updates WHERE timestamp < ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()


_db_instance: Optional[Database] = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
