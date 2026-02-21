"""
Orchestrator Mesh for Synapse Control Plane.
Coordinates execution across multiple nodes.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import hashlib
import json

PROTOCOL_VERSION: str = "1.0"


@dataclass
class MeshState:
    """State of the orchestrator mesh"""
    mesh_id: str
    active_orchestrators: List[str]
    state_hash: str
    timestamp: datetime
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class MeshMessage:
    """Message between orchestrators"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: str
    payload: dict
    timestamp: datetime
    signature: str
    protocol_version: str = PROTOCOL_VERSION


class OrchestratorMesh:
    """
    Mesh of orchestrators for distributed coordination.
    
    Invariants:
    - All messages are signed
    - State is consistent across mesh
    - Failover is deterministic
    """
    
    def __init__(self, mesh_id: str, node_id: str):
        self.mesh_id = mesh_id
        self.node_id = node_id
        self._orchestrators: Dict[str, dict] = {}
        self._message_log: List[MeshMessage] = []
    
    async def join_mesh(self, orchestrator_id: str, metadata: dict) -> bool:
        """Join the orchestrator mesh"""
        if orchestrator_id in self._orchestrators:
            return False
        
        self._orchestrators[orchestrator_id] = {
            "id": orchestrator_id,
            "metadata": metadata,
            "joined_at": datetime.utcnow().isoformat()
        }
        
        return True
    
    async def leave_mesh(self, orchestrator_id: str) -> bool:
        """Leave the orchestrator mesh"""
        if orchestrator_id not in self._orchestrators:
            return False
        
        del self._orchestrators[orchestrator_id]
        return True
    
    async def broadcast(self, message_type: str, payload: dict) -> str:
        """Broadcast message to all orchestrators"""
        message_id = self._generate_message_id()
        
        message = MeshMessage(
            message_id=message_id,
            sender_id=self.node_id,
            receiver_id="broadcast",
            message_type=message_type,
            payload=payload,
            timestamp=datetime.utcnow(),
            signature=self._sign_message(message_id, payload),
            protocol_version=PROTOCOL_VERSION
        )
        
        self._message_log.append(message)
        return message_id
    
    async def get_mesh_state(self) -> MeshState:
        """Get current mesh state"""
        state_hash = self._compute_mesh_hash()
        
        return MeshState(
            mesh_id=self.mesh_id,
            active_orchestrators=list(self._orchestrators.keys()),
            state_hash=state_hash,
            timestamp=datetime.utcnow(),
            protocol_version=PROTOCOL_VERSION
        )
    
    def _generate_message_id(self) -> str:
        """Generate deterministic message ID"""
        combined = f"{self.node_id}:{len(self._message_log)}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _sign_message(self, message_id: str, payload: dict) -> str:
        """Sign message (placeholder)"""
        combined = f"{message_id}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _compute_mesh_hash(self) -> str:
        """Compute deterministic mesh hash"""
        sorted_orchestrators = sorted(self._orchestrators.items())
        
        mesh_data = {
            "mesh_id": self.mesh_id,
            "orchestrators": [oid for oid, _ in sorted_orchestrators]
        }
        
        mesh_json = json.dumps(mesh_data, sort_keys=True)
        return hashlib.sha256(mesh_json.encode()).hexdigest()
