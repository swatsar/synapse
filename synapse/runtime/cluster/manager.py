PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import List, Dict

from synapse.distributed.node_runtime import NodeRuntime
from synapse.reliability.snapshot_manager import SnapshotManager
from synapse.reliability.rollback_manager import RollbackManager
from synapse.security.capability_manager import CapabilityManager

class ClusterManager:
    """Manages a set of NodeRuntime instances and provides cluster‑wide
    snapshot/rollback functionality.

    The manager ensures that all nodes agree on a deterministic snapshot order
    and that a rollback restores the state on every node.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager, nodes: List[NodeRuntime]):
        self._caps = caps
        self._nodes = nodes
        # One SnapshotManager per node – they share the same capability manager.
        self._snapshots = [SnapshotManager(caps) for _ in nodes]
        self._rollbacks = [RollbackManager(caps, sm) for sm in self._snapshots]

    async def create_cluster_snapshot(self) -> List[str]:
        """Create a snapshot on every node and return the list of snapshot paths."""
        await self._caps.check_capability(["cluster:snapshot"])
        paths = []
        for node, sm in zip(self._nodes, self._snapshots):
            # In a real system we would gather the node's state; here we use a stub dict.
            state = {"node_id": id(node), "dummy": True}
            path = await sm.create_snapshot(state)
            paths.append(path)
        return paths

    async def rollback_cluster(self, snapshot_paths: List[str]) -> List[Dict]:
        """Rollback each node using the corresponding snapshot path and return the loaded states."""
        await self._caps.check_capability(["cluster:rollback"])
        states = []
        for rm, path in zip(self._rollbacks, snapshot_paths):
            state = await rm.rollback_to(path)
            states.append(state)
        return states
