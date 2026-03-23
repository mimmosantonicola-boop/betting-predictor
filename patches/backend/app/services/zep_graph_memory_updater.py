"""
zep_graph_memory_updater.py — Patched to use local SQLite memory.
Original: stored agent activity text in Zep Cloud graph.
Patched:  stores the same text in local SQLite via local_zep.LocalZepClient.
"""

import logging
from .local_zep import get_zep_client

logger = logging.getLogger(__name__)


class ZepGraphMemoryUpdater:
    """
    Batches agent activity descriptions and persists them to the
    local graph memory store.
    """

    def __init__(self, graph_id: str, zep_client=None):
        self.graph_id = graph_id
        self._client = zep_client or get_zep_client()

    def update(self, activities: list[str]) -> None:
        """
        Combine a list of activity strings and store in the graph.

        Args:
            activities: List of strings like "AgentName: did something"
        """
        if not activities:
            return
        combined = "\n".join(str(a) for a in activities if a)
        if not combined.strip():
            return
        try:
            self._client.graph.add(
                graph_id=self.graph_id,
                type="text",
                data=combined,
            )
        except Exception as exc:
            logger.warning("Memory update failed (non-fatal): %s", exc)
