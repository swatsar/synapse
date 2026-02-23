"""
Phase 7: Distributed Execution Domain
Protocol Version: 1.0

Federates execution domains across nodes with:
- Domain identity across cluster
- Deterministic node assignment
- Cross-node replay compatibility
- Domain membership verification
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class NodeDescriptor:
    """Descriptor for a cluster node"""
    node_id: str
    node_name: str
    capabilities: List[str]
    resource_limits: Dict[str, int]
    endpoint: str
    registered_at: str = ""
    protocol_version: str = "1.0"
    
    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = datetime.utcnow().isoformat()


class DistributedExecutionDomain:
    """
    Federates execution domains across nodes.
    
    Provides:
    - Domain identity across cluster
    - Deterministic node assignment
    - Cross-node replay compatibility
    - Domain membership verification
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self):
        self._nodes: Dict[str, NodeDescriptor] = {}
        self._domain_memberships: Dict[str, List[str]] = {}  # domain_id -> [node_ids]
        self._node_domains: Dict[str, str] = {}  # node_id -> domain_id
    
    def register_node(self, node_descriptor: NodeDescriptor) -> str:
        """
        Register a node in the execution domain.
        
        Args:
            node_descriptor: Descriptor containing node configuration
            
        Returns:
            node_id: The registered node identifier
        """
        node_id = node_descriptor.node_id
        self._nodes[node_id] = node_descriptor
        return node_id
    
    def assign_execution(self, tenant_id: str, contract_id: str) -> str:
        """
        Assign execution to a node deterministically.
        
        Uses consistent hashing to ensure same tenant+contract
        always maps to same node.
        
        Args:
            tenant_id: Tenant identifier
            contract_id: Contract identifier
            
        Returns:
            node_id: The assigned node identifier
        """
        if not self._nodes:
            raise ValueError("No nodes registered in domain")
        
        # Deterministic assignment using consistent hashing
        assignment_key = f"{tenant_id}:{contract_id}"
        hash_value = hashlib.sha256(assignment_key.encode()).hexdigest()
        
        # Get sorted node IDs for deterministic selection
        node_ids = sorted(self._nodes.keys())
        
        # Select node based on hash
        node_index = int(hash_value[:8], 16) % len(node_ids)
        return node_ids[node_index]
    
    def verify_domain_integrity(self, domain_id: str) -> bool:
        """
        Verify integrity of a domain.
        
        Args:
            domain_id: Domain identifier
            
        Returns:
            bool: True if domain integrity is valid
        """
        # Check if domain exists
        if domain_id not in self._domain_memberships:
            # Domain doesn't exist yet - valid for new domains
            return True
        
        # Verify all nodes in domain are still registered
        node_ids = self._domain_memberships[domain_id]
        for node_id in node_ids:
            if node_id not in self._nodes:
                return False
        
        return True
    
    def get_node(self, node_id: str) -> Optional[NodeDescriptor]:
        """Get node descriptor by ID"""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeDescriptor]:
        """Get all registered nodes"""
        return list(self._nodes.values())
    
    def compute_domain_hash(self) -> str:
        """
        Compute deterministic hash of domain state.
        
        Returns:
            str: SHA-256 hash of domain state
        """
        domain_state = {
            "nodes": sorted([
                {
                    "node_id": n.node_id,
                    "capabilities": sorted(n.capabilities),
                    "endpoint": n.endpoint
                }
                for n in self._nodes.values()
            ], key=lambda x: x["node_id"]),
            "protocol_version": self.PROTOCOL_VERSION
        }
        
        canonical = json.dumps(domain_state, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
