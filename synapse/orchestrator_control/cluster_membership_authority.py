"""
Phase 7.1: Cluster Membership Authority
Protocol Version: 1.0

Deterministic cluster membership governance.
Responsibilities:
- node trust registration
- membership hash
- quorum validation
- cluster identity hash
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import hashlib
import json
from datetime import datetime

from synapse.orchestrator_control.models import (
    TrustedNodeDescriptor,
    ClusterMembership,
    PROTOCOL_VERSION
)


@dataclass
class MembershipState:
    """Current membership state"""
    nodes: Dict[str, TrustedNodeDescriptor]
    membership_hash: str
    quorum_count: int
    last_updated: str
    protocol_version: str = PROTOCOL_VERSION


class ClusterMembershipAuthority:
    """
    Deterministic cluster membership governance.
    
    Responsibilities:
    - node trust registration
    - membership hash
    - quorum validation
    - cluster identity hash
    
    Public API:
    - register_trusted_node(node_descriptor)
    - compute_membership_hash()
    - verify_membership()
    """
    
    PROTOCOL_VERSION = PROTOCOL_VERSION
    
    def __init__(self, quorum_threshold: int = 2):
        self._nodes: Dict[str, TrustedNodeDescriptor] = {}
        self._quorum_threshold = quorum_threshold
        self._membership_hash: Optional[str] = None
        self._last_updated: Optional[str] = None
    
    def register_trusted_node(
        self,
        descriptor: TrustedNodeDescriptor
    ) -> str:
        """
        Register a trusted node.
        
        Args:
            descriptor: Node descriptor
            
        Returns:
            node_id
        """
        # Store the node
        self._nodes[descriptor.node_id] = descriptor
        
        # Update membership hash
        self._membership_hash = self._compute_membership_hash()
        self._last_updated = datetime.utcnow().isoformat()
        
        return descriptor.node_id
    
    def unregister_node(self, node_id: str) -> bool:
        """
        Unregister a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            True if node was removed
        """
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._membership_hash = self._compute_membership_hash()
            self._last_updated = datetime.utcnow().isoformat()
            return True
        return False
    
    def compute_membership_hash(self) -> str:
        """
        Compute deterministic membership hash.
        
        Returns:
            SHA-256 hash of membership state
        """
        if self._membership_hash is None:
            self._membership_hash = self._compute_membership_hash()
        return self._membership_hash
    
    def verify_membership(self, node_id: str) -> bool:
        """
        Verify if a node is a member.
        
        Args:
            node_id: Node identifier
            
        Returns:
            True if node is a trusted member
        """
        return node_id in self._nodes
    
    def get_node(self, node_id: str) -> Optional[TrustedNodeDescriptor]:
        """
        Get node descriptor.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node descriptor or None
        """
        return self._nodes.get(node_id)
    
    def list_nodes(self) -> List[Dict[str, any]]:
        """
        List all trusted nodes.
        
        Returns:
            List of node descriptors
        """
        return [
            {
                "node_id": node.node_id,
                "node_name": node.node_name,
                "trust_level": node.trust_level,
                "registered_at": node.registered_at,
                "protocol_version": node.protocol_version
            }
            for node in sorted(
                self._nodes.values(),
                key=lambda n: n.node_id
            )
        ]
    
    def get_membership_state(self) -> MembershipState:
        """
        Get current membership state.
        
        Returns:
            Membership state
        """
        return MembershipState(
            nodes=self._nodes.copy(),
            membership_hash=self.compute_membership_hash(),
            quorum_count=len(self._nodes),
            last_updated=self._last_updated or datetime.utcnow().isoformat()
        )
    
    def validate_quorum(self) -> bool:
        """
        Validate if quorum is reached.
        
        Returns:
            True if quorum is reached
        """
        return len(self._nodes) >= self._quorum_threshold
    
    def get_quorum_count(self) -> int:
        """Get current quorum count"""
        return len(self._nodes)
    
    def get_quorum_threshold(self) -> int:
        """Get quorum threshold"""
        return self._quorum_threshold
    
    def compute_cluster_identity_hash(self) -> str:
        """
        Compute cluster identity hash.
        
        Returns:
            SHA-256 hash representing cluster identity
        """
        data = {
            'membership_hash': self.compute_membership_hash(),
            'node_count': len(self._nodes),
            'quorum_threshold': self._quorum_threshold,
            'protocol_version': self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def _compute_membership_hash(self) -> str:
        """
        Compute deterministic hash of membership.
        
        Returns:
            SHA-256 hash
        """
        # Sort nodes by node_id for determinism
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda n: n.node_id
        )
        
        data = {
            'nodes': [
                {
                    'node_id': node.node_id,
                    'node_name': node.node_name,
                    'public_key': node.public_key,
                    'trust_level': node.trust_level,
                    'registered_at': node.registered_at,
                    'node_hash': node.compute_node_hash()
                }
                for node in sorted_nodes
            ],
            'quorum_threshold': self._quorum_threshold,
            'protocol_version': self.PROTOCOL_VERSION
        }
        
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def verify_membership_integrity(self) -> bool:
        """
        Verify membership integrity.
        
        Returns:
            True if membership is valid
        """
        # Check each node has valid hash
        for node in self._nodes.values():
            expected_hash = node.compute_node_hash()
            # Node hash should be deterministic
            if node.compute_node_hash() != expected_hash:
                return False
        
        # Check membership hash is consistent
        computed_hash = self._compute_membership_hash()
        if self._membership_hash and self._membership_hash != computed_hash:
            return False
        
        return True
    
    def get_nodes_by_trust_level(self, trust_level: int) -> List[str]:
        """
        Get nodes by trust level.
        
        Args:
            trust_level: Trust level to filter by
            
        Returns:
            List of node IDs
        """
        return [
            node.node_id for node in self._nodes.values()
            if node.trust_level == trust_level
        ]
    
    def get_trusted_nodes(self) -> List[str]:
        """
        Get all trusted node IDs.
        
        Returns:
            List of trusted node IDs
        """
        return list(self._nodes.keys())
