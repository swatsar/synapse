PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Any, Dict, List

from synapse.memory.store import MemoryStore
from synapse.security.capability_manager import CapabilityManager

class DistributedMemoryStore:
    """Thin async wrapper around the core ``MemoryStore`` that pretends to be
    distributed.  In a real deployment it would replicate data across nodes.
    For the purpose of this phase it forwards calls to a local ``MemoryStore``
    and enforces capability checks.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._store = MemoryStore()

    async def add_long_term(self, category: str, data: Any) -> None:
        await self._caps.check_capability(["memory:write"])
        await self._store.add_long_term(category, data)

    async def query(self, query: str, limit: int = 10) -> List[Dict]:
        await self._caps.check_capability(["memory:read"])
        return await self._store.query_long_term(query)

    # Stub for replication – in a real system this would push changes to peers.
    async def replicate(self) -> None:
        await self._caps.check_capability(["memory:replicate"])
        # No‑op for now.
        await asyncio.sleep(0)
