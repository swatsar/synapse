PROTOCOL_VERSION: str = "1.0"
import asyncio

from synapse.security.capability_manager import CapabilityManager


class ReplicationManager:
    """Replicates arbitrary payloads to a list of peer node identifiers.

    In this stub implementation the replication is simulated by storing the
    payloads in an in‑memory dictionary keyed by ``node_id``.  Real code would
    use network transport (e.g., gRPC, HTTP) to push data.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._store: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()

    async def replicate(self, target_node: str, payload: dict) -> None:
        await self._caps.check_capability(["replication:send"])
        async with self._lock:
            self._store.setdefault(target_node, []).append(payload)

    async def fetch_replications(self, node_id: str) -> list[dict]:
        await self._caps.check_capability(["replication:receive"])
        async with self._lock:
            return list(self._store.get(node_id, []))
