PROTOCOL_VERSION: str = "1.0"
import asyncio
import os
import json
import datetime
from typing import Any, Dict

from synapse.security.capability_manager import CapabilityManager

class SnapshotManager:
    """Create and restore deterministic snapshots of the system state.

    Snapshots are stored as JSON files in ``.snapshots`` under the project root.
    The manager checks capabilities before writing or loading a snapshot.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager, base_path: str = "/a0/usr/projects/project_synapse"):
        self._caps = caps
        self._snap_dir = os.path.join(base_path, ".snapshots")
        os.makedirs(self._snap_dir, exist_ok=True)

    async def create_snapshot(self, state: Dict[str, Any]) -> str:
        """Persist ``state`` to a timestamped JSON file and return its path."""
        await self._caps.check_capability(["snapshot:create"])
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = os.path.join(self._snap_dir, f"snapshot_{ts}.json")

        def _write_file():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

        await asyncio.to_thread(_write_file)
        return path

    async def restore_snapshot(self, path: str) -> Dict[str, Any]:
        """Load a snapshot file and return the stored state."""
        await self._caps.check_capability(["snapshot:restore"])

        def _read_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        return await asyncio.to_thread(_read_file)
