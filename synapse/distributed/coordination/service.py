PROTOCOL_VERSION: str = "1.0"
import asyncio
import time
from typing import Any, Dict, List

from synapse.security.capability_manager import CapabilityManager

class ClusterCoordinationService:
    """Deterministic coordination service for a cluster of nodes.

    Nodes register themselves and broadcast events.  Events are stored in a
    shared in‑memory log (simulated here) and ordered by a monotonically
    increasing timestamp.  The service checks capabilities before allowing a
    node to publish or consume events.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._node_registry: List[str] = []
        self._event_log: List[Dict] = []
        self._log_lock = asyncio.Lock()

    async def register_node(self, node_id: str) -> None:
        await self._caps.check_capability(["coordination:register"])
        async with self._log_lock:
            if node_id not in self._node_registry:
                self._node_registry.append(node_id)

    async def broadcast(self, node_id: str, payload: Dict) -> None:
        await self._caps.check_capability(["coordination:broadcast"])
        async with self._log_lock:
            event = {
                "timestamp": time.time(),
                "node_id": node_id,
                "payload": payload,
                "protocol_version": self.protocol_version,
            }
            self._event_log.append(event)

    async def fetch_log(self) -> List[Dict]:
        await self._caps.check_capability(["coordination:read"])
        async with self._log_lock:
            # Return a copy to avoid external mutation
            return list(self._event_log)
