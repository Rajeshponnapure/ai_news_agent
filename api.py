"""Optional FastAPI layer for querying updates and triggering jobs manually."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import settings
from database.db import get_db
from processing.pipeline import ProcessingPipeline
from ingestion.manager import IngestionManager

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Update Agent", version="1.0.0")

IST = timezone(timedelta(hours=5, minutes=30))


# ── Models ────────────────────────────────────────────────────────────────────


class UpdateResponse(BaseModel):
    id: str
    title: str
    company: str
    summary: str
    timestamp: str
    impact_level: str
    source_url: str
    digest_sent: bool


class IngestResponse(BaseModel):
    new_entries: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "time_ist": datetime.now(IST).isoformat()}


@app.get("/updates", response_model=list[UpdateResponse])
def list_updates(hours: int = 24, impact: str | None = None, limit: int = 50):
    """Return updates from the last N hours."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = db._get_conn()
    try:
        query = "SELECT * FROM updates WHERE timestamp >= ?"
        params: list = [cutoff]
        if impact:
            query += " AND impact_level = ?"
            params.append(impact)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [
            UpdateResponse(
                id=r["id"],
                title=r["title"],
                company=r["company"],
                summary=r["summary"],
                timestamp=r["timestamp"],
                impact_level=r["impact_level"],
                source_url=r["source_url"],
                digest_sent=bool(r["digest_sent"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


@app.post("/ingest", response_model=IngestResponse)
def trigger_ingest():
    """Manually trigger an ingestion cycle."""
    manager = IngestionManager()
    try:
        count = manager.run()
        return IngestResponse(new_entries=count)
    finally:
        manager.close()


@app.get("/stats")
def stats():
    """Return database statistics."""
    db = get_db()
    conn = db._get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0]
        unsent = conn.execute("SELECT COUNT(*) FROM updates WHERE digest_sent = 0").fetchone()[0]
        high = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE impact_level = 'high' AND digest_sent = 0"
        ).fetchone()[0]
        last_24h = conn.execute(
            "SELECT COUNT(*) FROM updates WHERE timestamp >= ?",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),),
        ).fetchone()[0]
        return {"total": total, "unsent": unsent, "high_impact_unsent": high, "last_24h": last_24h}
    finally:
        conn.close()
