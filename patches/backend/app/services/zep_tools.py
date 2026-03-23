"""
zep_tools.py — Patched to use local SQLite memory.
Provides the three retrieval tool functions used by the ReportAgent:
  - InsightForge  (deep hybrid search)
  - PanoramaSearch (full breadth search)
  - QuickSearch   (lightweight search)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .local_zep import get_zep_client, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class InsightResult:
    query: str
    facts: list
    entities: list
    relationship_chains: list
    raw_results: list = field(default_factory=list)


@dataclass
class PanoramaResult:
    active_facts: list
    historical_facts: list
    all_nodes: list
    all_edges: list
    summary: str = ""


class ZepTools:
    """
    Retrieval tools for the ReportAgent.
    Backed by local SQLite full-text search.
    """

    def __init__(self, graph_id: str, simulation_id: Optional[str] = None,
                 zep_client=None):
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self._client = zep_client or get_zep_client()

    # ── InsightForge ─────────────────────────────────────────────────────────

    def InsightForge(self, query: str, limit: int = 15) -> InsightResult:
        """
        Deep hybrid retrieval.
        Runs the primary query plus auto-generated sub-queries,
        merges results and extracts entity context.
        """
        # Primary search
        primary = self._search(query, limit)

        # Auto-generate sub-questions for richer coverage
        sub_queries = self._generate_sub_queries(query)
        sub_results = []
        for sq in sub_queries:
            sub_results.extend(self._search(sq, limit=5))

        all_results = self._deduplicate(primary + sub_results)

        # Extract entity names mentioned in results
        entities = self._extract_entities_from_results(all_results)

        # Build relationship chains (pairs of entities that co-occur)
        chains = self._build_chains(all_results)

        return InsightResult(
            query=query,
            facts=[r.fact for r in all_results[:limit]],
            entities=entities,
            relationship_chains=chains,
            raw_results=all_results,
        )

    # ── PanoramaSearch ────────────────────────────────────────────────────────

    def PanoramaSearch(self, topic: str = "") -> PanoramaResult:
        """
        Breadth-first retrieval — returns everything stored for this graph.
        """
        nodes, _ = self._client.graph.get_all_nodes(self.graph_id, limit=200)
        edges, _ = self._client.graph.get_all_edges(self.graph_id, limit=200)

        facts = [r.fact for r in self._search(topic or "match prediction", limit=50)]

        # Split into "active" (recent half) and "historical" (older half)
        mid = max(1, len(facts) // 2)
        active = facts[:mid]
        historical = facts[mid:]

        summary = (
            f"Graph contains {len(nodes)} entities and {len(edges)} relationships. "
            f"{len(facts)} relevant text chunks found."
        )

        return PanoramaResult(
            active_facts=active,
            historical_facts=historical,
            all_nodes=[{"uuid": n.uuid, "name": n.name, "labels": n.labels,
                        "summary": n.summary} for n in nodes],
            all_edges=[{"uuid": e.uuid, "fact": e.fact,
                        "source": e.source_node_uuid,
                        "target": e.target_node_uuid} for e in edges],
            summary=summary,
        )

    # ── QuickSearch ───────────────────────────────────────────────────────────

    def QuickSearch(self, query: str, limit: int = 10) -> list[dict]:
        """Lightweight search — returns a plain list of fact strings."""
        results = self._search(query, limit)
        return [
            {
                "fact": r.fact,
                "score": r.score,
                "uuid": r.uuid,
                "created_at": r.created_at,
            }
            for r in results
        ]

    # ── Utility methods (also called by simulation.py) ────────────────────────

    def search_graph(self, query: str, limit: int = 10) -> list:
        return self._search(query, limit)

    def get_all_nodes(self) -> list:
        nodes, _ = self._client.graph.get_all_nodes(self.graph_id, limit=500)
        return nodes

    def get_all_edges(self) -> list:
        edges, _ = self._client.graph.get_all_edges(self.graph_id, limit=500)
        return edges

    def get_node_detail(self, node_uuid: str):
        return self._client.graph.get_node(self.graph_id, node_uuid)

    def get_node_edges(self, node_uuid: str) -> list:
        return self._client.graph.get_node_edges(self.graph_id, node_uuid)

    def get_entities_by_type(self, entity_type: str) -> list:
        return self._client.graph.get_nodes_by_type(self.graph_id, entity_type)

    def get_entity_summary(self, node_uuid: str) -> str:
        node = self._client.graph.get_node(self.graph_id, node_uuid)
        if node and node.summary:
            return node.summary
        return ""

    # ── Interview stub ────────────────────────────────────────────────────────

    def interview_agents(self, question: str, agent_ids: Optional[list] = None,
                         simulation_id: Optional[str] = None) -> list:
        """
        Stub — returns stored context as interview 'responses'.
        Real multi-perspective interviews require a running OASIS environment.
        """
        results = self._search(question, limit=5)
        return [
            {"agent": "context", "response": r.fact, "score": r.score}
            for r in results
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            return self._client.graph.search(self.graph_id, query, limit)
        except Exception as exc:
            logger.warning("Search failed: %s", exc)
            return []

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        seen = set()
        out = []
        for r in results:
            key = r.fact[:100]
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    @staticmethod
    def _generate_sub_queries(query: str) -> list[str]:
        """Heuristic sub-question generation for richer recall."""
        words = query.lower().split()
        subs = []
        if any(w in words for w in ["win", "result", "score"]):
            subs.append("match outcome prediction probability")
        if any(w in words for w in ["goal", "goals", "over", "under"]):
            subs.append("goals expected scoring both teams")
        if any(w in words for w in ["corner", "corners"]):
            subs.append("corners set pieces attacking pressure")
        if any(w in words for w in ["card", "foul", "yellow", "red"]):
            subs.append("yellow red cards discipline fouls")
        if not subs:
            subs.append(f"{query} analysis expert opinion")
        return subs[:3]

    @staticmethod
    def _extract_entities_from_results(results: list[SearchResult]) -> list[str]:
        import re
        entities = set()
        pattern = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
        for r in results[:10]:
            entities.update(pattern.findall(r.fact))
        return list(entities)[:20]

    @staticmethod
    def _build_chains(results: list[SearchResult]) -> list[dict]:
        chains = []
        for r in results[:5]:
            chains.append({
                "source": r.source_node_uuid,
                "target": r.target_node_uuid,
                "fact": r.fact[:200],
            })
        return chains
