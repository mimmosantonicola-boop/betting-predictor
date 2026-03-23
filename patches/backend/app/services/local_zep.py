"""
local_zep.py — Local SQLite replacement for Zep Cloud memory service.

Implements the minimal Zep API surface used by MiroFish:
  - client.graph.add(graph_id, type, data)
  - client.graph.search(graph_id, query, limit)
  - Paginated node / edge retrieval
  - Single node / edge lookup

No external services or API keys required.
"""

import re
import json
import uuid
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes (mirror Zep's public types) ──────────────────────────────────

@dataclass
class NodeInfo:
    uuid: str
    name: str
    labels: list
    summary: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    created_at: str = ""


@dataclass
class EdgeInfo:
    uuid: str
    source_node_uuid: str
    target_node_uuid: str
    fact: str
    created_at: str
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None


@dataclass
class SearchResult:
    uuid: str
    fact: str
    score: float
    source_node_uuid: str
    target_node_uuid: str
    created_at: str
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None


# ── Graph client ──────────────────────────────────────────────────────────────

class LocalGraphClient:
    """SQLite-backed graph store. Drop-in for Zep's graph client."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS graph_texts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id  TEXT    NOT NULL,
                    chunk_id  TEXT    NOT NULL UNIQUE,
                    data      TEXT    NOT NULL,
                    created_at TEXT   NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id   TEXT NOT NULL,
                    node_uuid  TEXT NOT NULL UNIQUE,
                    name       TEXT NOT NULL,
                    labels     TEXT NOT NULL,
                    summary    TEXT,
                    attributes TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id     TEXT NOT NULL,
                    edge_uuid    TEXT NOT NULL UNIQUE,
                    source_uuid  TEXT NOT NULL,
                    target_uuid  TEXT NOT NULL,
                    fact         TEXT NOT NULL,
                    created_at   TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS graph_fts
                    USING fts5(chunk_id UNINDEXED, data,
                               content='graph_texts', content_rowid='id');
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Write ─────────────────────────────────────────────────────────────────

    def add(self, graph_id: str, type: str = "text", data: str = "") -> None:
        """Store text and extract lightweight entities."""
        if not data:
            return
        chunk_id = str(uuid.uuid4())
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO graph_texts (graph_id, chunk_id, data, created_at) VALUES (?,?,?,?)",
                (graph_id, chunk_id, data, now),
            )
            try:
                conn.execute(
                    "INSERT INTO graph_fts(rowid, chunk_id, data) "
                    "SELECT id, chunk_id, data FROM graph_texts WHERE chunk_id=?",
                    (chunk_id,),
                )
            except sqlite3.Error:
                pass  # FTS rebuild will catch it on next search
        self._extract_entities(graph_id, data, now)

    def _extract_entities(self, graph_id: str, text: str, timestamp: str):
        """Extract agent activity lines as nodes (AgentName: action)."""
        pattern = re.compile(r"^([A-Za-z][A-Za-z\s]{1,40}):\s+(.+)$")
        with self._conn() as conn:
            for line in text.splitlines():
                m = pattern.match(line.strip())
                if not m:
                    continue
                agent_name = m.group(1).strip()
                action = m.group(2).strip()
                node_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{graph_id}:{agent_name}"))
                conn.execute(
                    """INSERT OR IGNORE INTO graph_nodes
                       (graph_id, node_uuid, name, labels, summary, attributes, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        graph_id, node_uuid, agent_name,
                        json.dumps(["Entity", "Agent"]),
                        action[:300],
                        json.dumps({}),
                        timestamp,
                    ),
                )

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, graph_id: str, query: str, limit: int = 10) -> list:
        """Full-text search; falls back to LIKE if FTS fails."""
        results = []
        with self._conn() as conn:
            try:
                safe_q = " ".join(
                    f'"{w}"' for w in query.split() if w
                )
                rows = conn.execute(
                    """SELECT t.chunk_id, t.data, t.created_at
                       FROM graph_fts f
                       JOIN graph_texts t ON t.chunk_id = f.chunk_id
                       WHERE f.data MATCH ? AND t.graph_id = ?
                       LIMIT ?""",
                    (safe_q, graph_id, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """SELECT chunk_id, data, created_at FROM graph_texts
                       WHERE graph_id = ? AND data LIKE ?
                       LIMIT ?""",
                    (graph_id, f"%{query[:50]}%", limit),
                ).fetchall()

        for i, (chunk_id, data, created_at) in enumerate(rows):
            results.append(
                SearchResult(
                    uuid=chunk_id,
                    fact=data[:600],
                    score=max(0.1, 1.0 - i * 0.08),
                    source_node_uuid=chunk_id,
                    target_node_uuid=chunk_id,
                    created_at=created_at,
                )
            )
        return results

    # ── Node queries ──────────────────────────────────────────────────────────

    def get_all_nodes(self, graph_id: str, limit: int = 100,
                      cursor: Optional[str] = None):
        """Paginated node retrieval. Returns (nodes, next_cursor)."""
        offset = int(cursor) if cursor and cursor.isdigit() else 0
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT node_uuid, name, labels, summary, attributes, created_at
                   FROM graph_nodes WHERE graph_id = ?
                   LIMIT ? OFFSET ?""",
                (graph_id, limit, offset),
            ).fetchall()

        nodes = [
            NodeInfo(
                uuid=r[0], name=r[1],
                labels=json.loads(r[2]),
                summary=r[3],
                attributes=json.loads(r[4]) if r[4] else {},
                created_at=r[5],
            )
            for r in rows
        ]
        next_cursor = str(offset + limit) if len(rows) == limit else None
        return nodes, next_cursor

    def get_node(self, graph_id: str, node_uuid: str) -> Optional[NodeInfo]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT node_uuid, name, labels, summary, attributes, created_at
                   FROM graph_nodes WHERE graph_id = ? AND node_uuid = ?""",
                (graph_id, node_uuid),
            ).fetchone()
        if not row:
            return None
        return NodeInfo(
            uuid=row[0], name=row[1],
            labels=json.loads(row[2]),
            summary=row[3],
            attributes=json.loads(row[4]) if row[4] else {},
            created_at=row[5],
        )

    def get_nodes_by_type(self, graph_id: str, entity_type: str,
                          limit: int = 50) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT node_uuid, name, labels, summary, attributes, created_at
                   FROM graph_nodes WHERE graph_id = ? AND labels LIKE ?
                   LIMIT ?""",
                (graph_id, f"%{entity_type}%", limit),
            ).fetchall()
        return [
            NodeInfo(
                uuid=r[0], name=r[1],
                labels=json.loads(r[2]),
                summary=r[3],
                attributes=json.loads(r[4]) if r[4] else {},
                created_at=r[5],
            )
            for r in rows
        ]

    # ── Edge queries ──────────────────────────────────────────────────────────

    def get_all_edges(self, graph_id: str, limit: int = 100,
                      cursor: Optional[str] = None):
        """Paginated edge retrieval. Returns (edges, next_cursor)."""
        offset = int(cursor) if cursor and cursor.isdigit() else 0
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT edge_uuid, source_uuid, target_uuid, fact, created_at
                   FROM graph_edges WHERE graph_id = ?
                   LIMIT ? OFFSET ?""",
                (graph_id, limit, offset),
            ).fetchall()

        edges = [
            EdgeInfo(
                uuid=r[0],
                source_node_uuid=r[1],
                target_node_uuid=r[2],
                fact=r[3],
                created_at=r[4],
            )
            for r in rows
        ]
        next_cursor = str(offset + limit) if len(rows) == limit else None
        return edges, next_cursor

    def get_node_edges(self, graph_id: str, node_uuid: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT edge_uuid, source_uuid, target_uuid, fact, created_at
                   FROM graph_edges
                   WHERE graph_id = ?
                     AND (source_uuid = ? OR target_uuid = ?)""",
                (graph_id, node_uuid, node_uuid),
            ).fetchall()
        return [
            EdgeInfo(uuid=r[0], source_node_uuid=r[1],
                     target_node_uuid=r[2], fact=r[3], created_at=r[4])
            for r in rows
        ]

    # ── Convenience ───────────────────────────────────────────────────────────

    def get_all_text(self, graph_id: str) -> str:
        """Return all stored text for a graph (for context injection)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM graph_texts WHERE graph_id = ? ORDER BY id",
                (graph_id,),
            ).fetchall()
        return "\n\n".join(r[0] for r in rows)


# ── Top-level client ──────────────────────────────────────────────────────────

class LocalZepClient:
    """Drop-in replacement for `ZepClient` from zep_cloud SDK."""

    def __init__(self, api_key: str = "", db_path: str = "./data/local_memory.db"):
        self.graph = LocalGraphClient(db_path)
        self._api_key = api_key  # unused, kept for signature compatibility


def get_zep_client(db_path: str = "./data/local_memory.db") -> LocalZepClient:
    """Factory — use this everywhere instead of ZepClient(api_key=...)."""
    from app import config  # imported lazily to avoid circular deps
    path = getattr(config, "LOCAL_ZEP_DB_PATH", db_path)
    return LocalZepClient(db_path=path)
