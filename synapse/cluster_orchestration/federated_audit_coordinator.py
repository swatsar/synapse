"""
Phase 7: Federated Audit Coordinator
Protocol Version: 1.0

Aggregates audit roots from multiple nodes with:
- Node audit root collection
- Cluster Merkle root computation
- Cross-node replay verification
- Global execution proof
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class FederatedAuditRoot:
    """Aggregated audit root from multiple nodes"""
    aggregation_id: str
    timestamp: str
    node_roots: Dict[str, str]  # node_id -> merkle_root
    global_root: str
    protocol_version: str = "1.0"


class FederatedAuditCoordinator:
    """
    Aggregates audit roots from multiple nodes.
    
    Provides:
    - Node audit root collection
    - Cluster Merkle root computation
    - Cross-node replay verification
    - Global execution proof
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self):
        self._node_roots: Dict[str, str] = {}  # node_id -> merkle_root
        self._aggregation_history: List[FederatedAuditRoot] = []
        self._aggregation_counter = 0
    
    def collect_node_root(self, node_id: str, audit_root: str) -> None:
        """
        Collect audit root from a node.
        
        Args:
            node_id: Node identifier
            audit_root: Merkle root from node's audit chain
        """
        self._node_roots[node_id] = audit_root
    
    def compute_cluster_root(self) -> str:
        """
        Compute cluster-wide Merkle root from all node roots.
        
        Returns:
            str: SHA-256 hash of aggregated roots
        """
        if not self._node_roots:
            return hashlib.sha256(b'empty').hexdigest()
        
        # Sort node IDs for deterministic ordering
        sorted_nodes = sorted(self._node_roots.keys())
        
        # Build canonical representation
        root_data = {
            "nodes": [
                {"node_id": node_id, "root": self._node_roots[node_id]}
                for node_id in sorted_nodes
            ],
            "protocol_version": self.PROTOCOL_VERSION
        }
        
        canonical = json.dumps(root_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def verify_cluster_integrity(self) -> bool:
        """
        Verify integrity of the cluster audit.
        
        Returns:
            bool: True if cluster integrity is valid
        """
        # Check if we have any roots
        if not self._node_roots:
            return True  # Empty cluster is valid
        
        # Verify all roots are valid SHA-256 hashes
        for node_id, root in self._node_roots.items():
            if not self._is_valid_hash(root):
                return False
        
        return True
    
    def create_federated_root(self) -> FederatedAuditRoot:
        """
        Create a federated audit root snapshot.
        
        Returns:
            FederatedAuditRoot: Snapshot of current cluster state
        """
        self._aggregation_counter += 1
        
        federated_root = FederatedAuditRoot(
            aggregation_id=f"federation_{self._aggregation_counter}",
            timestamp=datetime.utcnow().isoformat(),
            node_roots=dict(self._node_roots),
            global_root=self.compute_cluster_root()
        )
        
        self._aggregation_history.append(federated_root)
        return federated_root
    
    def get_node_root(self, node_id: str) -> Optional[str]:
        """Get audit root for a specific node"""
        return self._node_roots.get(node_id)
    
    def get_all_node_roots(self) -> Dict[str, str]:
        """Get all node roots"""
        return dict(self._node_roots)
    
    def get_aggregation_history(self) -> List[FederatedAuditRoot]:
        """Get history of all federations"""
        return list(self._aggregation_history)
    
    def clear_node_roots(self) -> None:
        """Clear all collected roots"""
        self._node_roots.clear()
    
    def remove_node_root(self, node_id: str) -> bool:
        """Remove a node's root"""
        if node_id in self._node_roots:
            del self._node_roots[node_id]
            return True
        return False
    
    def _is_valid_hash(self, hash_value: str) -> bool:
        """Check if string is valid SHA-256 hash"""
        if not isinstance(hash_value, str):
            return False
        if len(hash_value) != 64:
            return False
        try:
            int(hash_value, 16)
            return True
        except ValueError:
            return False
    
    def verify_cross_node_replay(self, 
                                  expected_roots: Dict[str, str]) -> bool:
        """
        Verify that current roots match expected roots.
        
        Args:
            expected_roots: Expected node_id -> root mapping
            
        Returns:
            bool: True if all roots match
        """
        if set(self._node_roots.keys()) != set(expected_roots.keys()):
            return False
        
        for node_id, expected_root in expected_roots.items():
            if self._node_roots.get(node_id) != expected_root:
                return False
        
        return True
