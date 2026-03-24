"""SQLite database for request logging and usage tracking."""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".proxai" / "requests.db"


def init_db():
    """Initialize the database and create tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL    NOT NULL,
                provider    TEXT    NOT NULL,
                model       TEXT,
                method      TEXT,
                path        TEXT,
                status_code INTEGER,
                input_tokens  INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd    REAL    DEFAULT 0.0,
                latency_ms  INTEGER,
                error       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_requests_timestamp
                ON requests(timestamp);
            CREATE INDEX IF NOT EXISTS idx_requests_provider
                ON requests(provider);
        """)


@contextmanager
def get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_request(
    provider: str,
    model: Optional[str],
    method: str,
    path: str,
    status_code: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    error: Optional[str] = None,
):
    """Log a proxied request to the database."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO requests
               (timestamp, provider, model, method, path, status_code,
                input_tokens, output_tokens, cost_usd, latency_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), provider, model, method, path, status_code,
             input_tokens, output_tokens, cost_usd, latency_ms, error),
        )


def get_stats(days: int = 30) -> dict:
    """Get aggregated usage statistics."""
    since = time.time() - (days * 86400)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                provider,
                COUNT(*) as requests,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cost_usd) as cost_usd,
                AVG(latency_ms) as avg_latency_ms,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
               FROM requests
               WHERE timestamp >= ?
               GROUP BY provider""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_requests(limit: int = 50) -> list:
    """Get the most recent requests."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM requests
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_today_stats() -> dict:
    """Get today's totals."""
    today_start = time.time() - (time.time() % 86400)
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as requests,
                SUM(input_tokens + output_tokens) as total_tokens,
                SUM(cost_usd) as cost_usd
               FROM requests
               WHERE timestamp >= ?""",
            (today_start,),
        ).fetchone()
    return dict(row) if row else {}
