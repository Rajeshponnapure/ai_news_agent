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
    is_launch INTEGER NOT NULL DEFAULT 0,
    is_top_company INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL DEFAULT 'AI TECH',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    digest_sent INTEGER NOT NULL DEFAULT 0,
    alert_sent INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_updates_timestamp ON updates(timestamp);
CREATE INDEX IF NOT EXISTS idx_updates_company ON updates(company);
CREATE INDEX IF NOT EXISTS idx_updates_impact ON updates(impact_level);
CREATE INDEX IF NOT EXISTS idx_updates_digest_sent ON updates(digest_sent);
CREATE INDEX IF NOT EXISTS idx_updates_alert_sent ON updates(alert_sent);
CREATE INDEX IF NOT EXISTS idx_updates_title_company ON updates(title, company);
CREATE INDEX IF NOT EXISTS idx_updates_is_launch ON updates(is_launch);
"""

# Migration: add new columns if upgrading from old schema
MIGRATIONS = [
    "ALTER TABLE updates ADD COLUMN is_launch INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE updates ADD COLUMN is_top_company INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE updates ADD COLUMN category TEXT NOT NULL DEFAULT 'AI TECH'",
    "ALTER TABLE updates ADD COLUMN alert_sent INTEGER NOT NULL DEFAULT 0",
]


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
            # Apply migrations safely (ignore if column already exists)
            for migration in MIGRATIONS:
                try:
                    conn.execute(migration)
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # Column already exists
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
        is_launch: bool = False,
        is_top_company: bool = False,
        category: str = "AI TECH",
    ) -> str:
        entry_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO updates
                    (id, title, company, summary, timestamp, impact_level,
                     source_url, source_name, is_launch, is_top_company, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, title, company, summary, timestamp, impact_level,
                 source_url, source_name, int(is_launch), int(is_top_company), category),
            )
            conn.commit()
            return entry_id
        finally:
            conn.close()

    def get_new_alerts(self) -> list[dict]:
        """Get high-impact launch events from top companies that haven't been alerted yet.
        This drives real-time notifications."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM updates
                WHERE alert_sent = 0
                  AND (
                      (is_launch = 1 AND is_top_company = 1)
                      OR impact_level = 'high'
                  )
                ORDER BY
                    CASE impact_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    timestamp DESC
                LIMIT 30
                """
            ).fetchall()
            return [dict(r) for r in rows]
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
                    is_launch DESC,
                    timestamp DESC
                """,
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_top_updates(self, limit: int = 50) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM updates
                WHERE timestamp >= ? AND digest_sent = 0
                ORDER BY
                    CASE impact_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    is_launch DESC,
                    is_top_company DESC,
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

    def mark_alert_sent(self, update_ids: list[str]):
        """Mark entries as alerted so they don't trigger duplicate alerts."""
        if not update_ids:
            return
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" for _ in update_ids)
            conn.execute(
                f"UPDATE updates SET alert_sent = 1 WHERE id IN ({placeholders})",
                update_ids,
            )
            conn.commit()
        finally:
            conn.close()

    def title_exists(self, title: str, company: str, hours: int = 48, source_name: str = "") -> bool:
        conn = self._get_conn()
        try:
            # Permanent exact-match first (prevents blog re-insertion)
            row = conn.execute(
                "SELECT 1 FROM updates WHERE title = ? AND company = ? LIMIT 1",
                (title, company),
            ).fetchone()
            if row is not None:
                return True
            # Time-window near-duplicate check
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
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
            conn.execute("DELETE FROM updates WHERE timestamp < ? AND digest_sent = 1", (cutoff,))
            conn.commit()
        finally:
            conn.close()


_db_instance: Optional[Database] = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
