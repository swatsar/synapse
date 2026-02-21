"""
Node Registry for Synapse Control Plane.
Maintains registry of all cluster nodes.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

PROTOCOL_VERSION: str = "1.0"


@dataclass
class NodeRegistration:
    """Node registration record"""
    node_id: str
    public_key: str
    certificate: str
    capabilities: List[str]
    registered_at: datetime
    status: str
    protocol_version: str = PROTOCOL_VERSION


class NodeRegistry:
    """
    Registry for cluster nodes.
    
    Invariants:
    - Node IDs are unique
    - All nodes have valid certificates
    - Registry state is hashable
    """
    
    def __init__(self):
        self._registrations: Dict[str, NodeRegistration] = {}
    
    async def register(self, registration: NodeRegistration) -> bool:
        """Register a new node"""
        if registration.node_id in self._registrations:
            return False
        
        if not await self._validate_registration(registration):
            return False
        
        self._registrations[registration.node_id] = registration
        return True
    
    async def unregister(self, node_id: str) -> bool:
        """Unregister a node"""
        if node_id not in self._registrations:
            return False
        
        del self._registrations[node_id]
        return True
    
    async def get_node(self, node_id: str) -> Optional[NodeRegistration]:
        """Get node by ID"""
        return self._registrations.get(node_id)
    
    async def list_nodes(self) -> List[NodeRegistration]:
        """List all registered nodes"""
        return list(self._registrations.values())
    
    async def get_registry_hash(self) -> str:
        """Get deterministic registry hash"""
        sorted_nodes = sorted(self._registrations.items(), key=lambda x: x[0])
        
        registry_data = "".join(
            f"{node_id}:{reg.certificate}"
            for node_id, reg in sorted_nodes
        )
        
        return hashlib.sha256(registry_data.encode()).hexdigest()
    
    async def _validate_registration(self, registration: NodeRegistration) -> bool:
        """Validate node registration"""
        return (
            len(registration.node_id) > 0 and
            len(registration.public_key) > 0 and
            len(registration.certificate) > 0
        )
