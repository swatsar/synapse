PROTOCOL_VERSION: str = "1.0"
import os
from typing import Dict

from .snapshot_manager import SnapshotManager
from synapse.security.capability_manager import CapabilityManager

class RollbackManager:
    """High‑level API to rollback the system to a previous snapshot.

    Uses ``SnapshotManager`` under the hood and validates the operation
    through ``CapabilityManager``.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager, snapshot_manager: SnapshotManager):
        self._caps = caps
        self._snap_mgr = snapshot_manager

    async def rollback_to(self, snapshot_path: str) -> Dict:
        """Restore the snapshot and return the loaded state."""
        await self._caps.check_capability(["rollback"])
        state = await self._snap_mgr.restore_snapshot(snapshot_path)
        # In a real system we would now push the state into MemoryStore, etc.
        return state
