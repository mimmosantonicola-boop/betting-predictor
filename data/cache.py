"""
data/cache.py — TTL-based cache backed by SQLite (local) or PostgreSQL (cloud).

On Render free tier there's no background worker, so we use a "lazy refresh"
pattern: data is fetched fresh when it's older than TTL, on-demand.

TTLs:
  - Odds:    60 minutes  (odds shift, but free API has 500 req/month budget)
  - News:    90 minutes
  - Fixtures: 6 hours
  - Standings: 24 hours
"""

from __future__ import annotations

import json
import os
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default TTLs in minutes
TTL = {
    "odds":       60,
    "news":       90,
    "fixtures":   360,
    "standings":  1440,
    "prediction": 10080,  # 7 days — predictions are expensive to regenerate
}

_DB_PATH = os.getenv("CACHE_DB_PATH", "./data/cache.db")


class Cache:
    """Simple key-value TTL cache using SQLite."""

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key        TEXT    PRIMARY KEY,
                    value      TEXT    NOT NULL,
                    expires_at TEXT    NOT NULL,
                    created_at TEXT    NOT NULL
                )
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if not expired, else None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        value_json, expires_at_str = row
        expires_at = datetime.fromisoformat(expires_at_str)
        if self._now() > expires_at:
            return None  # expired
        try:
            return json.loads(value_json)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl_minutes: int = 60) -> None:
        """Store value with expiry."""
        now = self._now()
        expires_at = now + timedelta(minutes=ttl_minutes)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache (key, value, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (key, json.dumps(value), expires_at.isoformat(), now.isoformat()),
            )

    def delete(self, key: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count deleted."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (self._now().isoformat(),),
            )
            return cur.rowcount

    def invalidate_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM cache WHERE key LIKE ?", (f"{prefix}%",)
            )
            return cur.rowcount

    # ── Convenience helpers ───────────────────────────────────────────────────

    def get_or_fetch(self, key: str, fetch_fn, ttl_minutes: int = 60) -> Any:
        """
        Return cached value if fresh, otherwise call fetch_fn(), cache and return it.
        fetch_fn must be a zero-argument callable.
        """
        cached = self.get(key)
        if cached is not None:
            logger.debug("Cache HIT: %s", key)
            return cached

        logger.debug("Cache MISS: %s — fetching...", key)
        value = fetch_fn()
        if value is not None:
            self.set(key, value, ttl_minutes)
        return value

    def age_minutes(self, key: str) -> Optional[float]:
        """Return how many minutes ago the key was cached (None if not cached)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT created_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        created_at = datetime.fromisoformat(row[0])
        delta = self._now() - created_at
        return delta.total_seconds() / 60


# Singleton instance
_cache: Optional[Cache] = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache
