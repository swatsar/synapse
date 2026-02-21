"""
Memory Vault - Immutable, Hash-Addressed, Capability-Protected Memory
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, UTC
import hashlib
import json


@dataclass(frozen=True)
class MemorySnapshot:
    """Immutable memory snapshot"""
    snapshot_id: str
    agent_id: str
    data: Dict[str, Any]
    capabilities_required: Set[str]
    created_at: str
    hash: str
    protocol_version: str = "1.0"


class MemoryVault:
    """Secure memory vault with hash-addressed storage"""
    
    def __init__(self):
        self._snapshots: Dict[str, MemorySnapshot] = {}
        self._agent_snapshots: Dict[str, List[str]] = {}
    
    def store(
        self,
        agent_id: str,
        data: Dict[str, Any],
        capabilities_required: Set[str]
    ) -> MemorySnapshot:
        """Store data in vault, returns immutable snapshot"""
        # Compute hash
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        data_hash = hashlib.sha256(canonical.encode()).hexdigest()
        
        # Create snapshot ID
        snapshot_id = hashlib.sha256(
            f"{agent_id}:{data_hash}:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Create immutable snapshot
        snapshot = MemorySnapshot(
            snapshot_id=snapshot_id,
            agent_id=agent_id,
            data=data,
            capabilities_required=frozenset(capabilities_required),
            created_at=datetime.now(UTC).isoformat(),
            hash=data_hash
        )
        
        # Store
        self._snapshots[snapshot_id] = snapshot
        
        if agent_id not in self._agent_snapshots:
            self._agent_snapshots[agent_id] = []
        self._agent_snapshots[agent_id].append(snapshot_id)
        
        return snapshot
    
    def retrieve(
        self,
        snapshot_id: str,
        capabilities: Set[str]
    ) -> Optional[MemorySnapshot]:
        """Retrieve snapshot if capabilities allow"""
        if snapshot_id not in self._snapshots:
            return None
        
        snapshot = self._snapshots[snapshot_id]
        
        # Check capabilities
        if not snapshot.capabilities_required.issubset(capabilities):
            return None
        
        return snapshot
    
    def get_agent_snapshots(self, agent_id: str) -> List[str]:
        """Get all snapshot IDs for an agent"""
        return self._agent_snapshots.get(agent_id, [])
    
    def verify_integrity(self, snapshot_id: str) -> bool:
        """Verify snapshot integrity"""
        if snapshot_id not in self._snapshots:
            return False
        
        snapshot = self._snapshots[snapshot_id]
        canonical = json.dumps(snapshot.data, sort_keys=True, separators=(',', ':'))
        computed_hash = hashlib.sha256(canonical.encode()).hexdigest()
        
        return computed_hash == snapshot.hash
    
    def detect_tampering(self, snapshot_id: str) -> bool:
        """Detect if snapshot has been tampered with"""
        return not self.verify_integrity(snapshot_id)
    
    def reconstruct(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Reconstruct data from snapshot"""
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot:
            return dict(snapshot.data)
        return None
    
    def get_snapshot_count(self) -> int:
        """Get total number of snapshots"""
        return len(self._snapshots)
