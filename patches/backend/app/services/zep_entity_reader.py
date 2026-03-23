"""
zep_entity_reader.py — Patched to use local SQLite memory.
Reads entities (nodes) and relationships (edges) from the local graph store.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .local_zep import get_zep_client, NodeInfo, EdgeInfo

logger = logging.getLogger(__name__)

# Entity type labels we consider "meaningful" (not generic graph infrastructure)
_GENERIC_LABELS = {"Entity", "Node"}

PREDEFINED_ENTITY_TYPES = [
    "Agent", "Team", "Player", "Coach", "Analyst",
    "Event", "Match", "Competition", "Prediction",
]


@dataclass
class EntityNode:
    uuid: str
    name: str
    labels: list
    summary: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    connected_nodes: list = field(default_factory=list)


@dataclass
class FilteredEntities:
    entities: list
    discovered_types: list
    total_nodes: int
    total_filtered: int


class ZepEntityReader:
    """
    Reads and filters entities from the local graph memory.
    Provides the same interface as the original Zep-based reader.
    """

    def __init__(self, graph_id: str, zep_client=None):
        self.graph_id = graph_id
        self._client = zep_client or get_zep_client()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_filtered_entities(
        self,
        enrich_edges: bool = False,
        entity_types: Optional[list] = None,
    ) -> FilteredEntities:
        """Return all non-generic nodes, optionally enriched with edges."""
        all_nodes = self._fetch_all_nodes()
        types = entity_types or PREDEFINED_ENTITY_TYPES
        filtered = [n for n in all_nodes if self._is_meaningful(n, types)]

        if enrich_edges:
            filtered = [self._enrich(n) for n in filtered]

        discovered = list({
            lbl
            for n in filtered
            for lbl in n.labels
            if lbl not in _GENERIC_LABELS
        })

        return FilteredEntities(
            entities=[self._to_entity_node(n) for n in filtered],
            discovered_types=discovered,
            total_nodes=len(all_nodes),
            total_filtered=len(filtered),
        )

    def get_entity(self, node_uuid: str) -> Optional[EntityNode]:
        """Get a single entity with full edge context."""
        node = self._client.graph.get_node(self.graph_id, node_uuid)
        if not node:
            return None
        enriched = self._enrich(node)
        return self._to_entity_node(enriched)

    def get_entities_by_type(self, entity_type: str) -> list:
        nodes = self._client.graph.get_nodes_by_type(self.graph_id, entity_type)
        return [self._to_entity_node(n) for n in nodes]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_all_nodes(self) -> list:
        nodes = []
        cursor = None
        for _ in range(20):  # max 20 pages of 100
            page, cursor = self._client.graph.get_all_nodes(
                self.graph_id, limit=100, cursor=cursor
            )
            nodes.extend(page)
            if not cursor:
                break
        return nodes

    def _is_meaningful(self, node: NodeInfo, types: list) -> bool:
        extra = set(node.labels) - _GENERIC_LABELS
        if extra:
            return True
        return any(t in node.labels for t in types)

    def _enrich(self, node: NodeInfo) -> NodeInfo:
        try:
            node.edges = self._client.graph.get_node_edges(
                self.graph_id, node.uuid
            )
        except Exception:
            node.edges = []
        return node

    def _to_entity_node(self, node: NodeInfo) -> EntityNode:
        return EntityNode(
            uuid=node.uuid,
            name=node.name,
            labels=node.labels,
            summary=node.summary,
            attributes=node.attributes,
            edges=getattr(node, "edges", []),
        )
