"""
Cluster Manager for Synapse Control Plane.
Manages node registration, health monitoring, and cluster state.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
import hashlib
import json

PROTOCOL_VERSION: str = "1.0"


@dataclass
class NodeInfo:
    """Information about a cluster node"""
    node_id: str
    public_key: str
    endpoint: str
    capabilities: List[str]
    registered_at: datetime
    last_heartbeat: datetime
    status: str = "active"
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ClusterState:
    """Current state of the cluster"""
    cluster_id: str
    nodes: Dict[str, NodeInfo]
    state_hash: str
    timestamp: datetime
    protocol_version: str = PROTOCOL_VERSION


class ClusterManager:
    """
    Manages cluster nodes and state.
    
    Invariants:
    - All nodes must be verified before registration
    - State hash is deterministic based on sorted node list
    - Heartbeat timeout triggers node removal
    """
    
    def __init__(self, cluster_id: str, heartbeat_timeout: int = 30):
        self.cluster_id = cluster_id
        self.heartbeat_timeout = heartbeat_timeout
        self._nodes: Dict[str, NodeInfo] = {}
        self._state_version = 0
    
    async def register_node(self, node: NodeInfo) -> bool:
        """Register a new node in the cluster"""
        if node.node_id in self._nodes:
            return False
        
        # Verify node identity (placeholder for cryptographic verification)
        if not await self._verify_node_identity(node):
            return False
        
        self._nodes[node.node_id] = node
        self._state_version += 1
        return True
    
    async def unregister_node(self, node_id: str) -> bool:
        """Remove a node from the cluster"""
        if node_id not in self._nodes:
            return False
        
        del self._nodes[node_id]
        self._state_version += 1
        return True
    
    async def update_heartbeat(self, node_id: str, timestamp: datetime) -> bool:
        """Update node heartbeat"""
        if node_id not in self._nodes:
            return False
        
        self._nodes[node_id].last_heartbeat = timestamp
        return True
    
    async def get_cluster_state(self) -> ClusterState:
        """Get current cluster state with deterministic hash"""
        state_hash = self._compute_state_hash()
        return ClusterState(
            cluster_id=self.cluster_id,
            nodes=dict(self._nodes),
            state_hash=state_hash,
            timestamp=datetime.utcnow(),
            protocol_version=PROTOCOL_VERSION
        )
    
    async def get_active_nodes(self) -> List[NodeInfo]:
        """Get list of active nodes"""
        now = datetime.utcnow()
        active = []
        
        for node in self._nodes.values():
            elapsed = (now - node.last_heartbeat).total_seconds()
            if elapsed < self.heartbeat_timeout:
                active.append(node)
        
        return sorted(active, key=lambda n: n.node_id)
    
    def _compute_state_hash(self) -> str:
        """Compute deterministic state hash"""
        # Sort nodes by ID for determinism
        sorted_nodes = sorted(self._nodes.items(), key=lambda x: x[0])
        
        state_data = {
            "cluster_id": self.cluster_id,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "capabilities": sorted(node.capabilities),
                    "status": node.status
                }
                for _, node in sorted_nodes
            ],
            "version": self._state_version
        }
        
        state_json = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    async def _verify_node_identity(self, node: NodeInfo) -> bool:
        """Verify node identity cryptographically"""
        # Placeholder for actual verification
        return len(node.node_id) > 0 and len(node.public_key) > 0
