PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Any, Dict, List

from synapse.security.capability_manager import CapabilityManager

class ConsensusEngine:
    """Very small deterministic consensus engine.

    Nodes provide a ``state`` dict.  The engine selects the node with the
    smallest identifier as the leader and returns its state as the agreed‑upon
    result.  This is deterministic and works without external libraries.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._states: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()

    async def propose(self, node_id: str, state: Dict) -> None:
        await self._caps.check_capability(["consensus:propose"])
        async with self._lock:
            self._states[node_id] = state

    async def decide(self) -> Dict:
        """Return the state of the elected leader (lowest node_id)."""
        await self._caps.check_capability(["consensus:decide"])
        async with self._lock:
            if not self._states:
                return {}
            leader = min(self._states.keys())
            return self._states[leader]
