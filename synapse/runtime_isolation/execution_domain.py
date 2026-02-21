"""
Execution Domain - Cryptographically identified execution scope

ExecutionDomain provides isolated execution boundaries with:
- Resource isolation between domains
- Capability scope limitation
- Memory isolation
- Deterministic execution context
"""

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Dict, Any
import hashlib
import json


@dataclass(frozen=True)
class ExecutionDomain:
    """
    Cryptographically identified execution domain.
    
    Guarantees:
    - Resources not shared between domains
    - Capability scope limited to domain
    - Memory isolated
    - Deterministic execution context
    """
    domain_id: str
    tenant_id: str
    capabilities: FrozenSet[str]
    state_hash: str
    protocol_version: str = "1.0"
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate domain after initialization"""
        if not self.domain_id:
            raise ValueError("domain_id is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
    
    def compute_state_hash(self) -> str:
        """
        Compute deterministic state hash for this domain.
        
        Note: Does NOT include node_id to ensure determinism across nodes.
        """
        hash_data = {
            "domain_id": self.domain_id,
            "tenant_id": self.tenant_id,
            "capabilities": sorted(list(self.capabilities)),
            "protocol_version": self.protocol_version
        }
        
        hash_json = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_json.encode()).hexdigest()
    
    def has_capability(self, capability: str) -> bool:
        """
        Check if domain has a specific capability.
        
        Supports wildcard matching:
        - "fs:read:/workspace/**" matches "fs:read:/workspace/file.txt"
        """
        for domain_cap in self.capabilities:
            if self._match_capability(domain_cap, capability):
                return True
        return False
    
    def _match_capability(self, pattern: str, capability: str) -> bool:
        """Match capability against pattern with wildcard support"""
        if pattern == capability:
            return True
        
        # Handle ** wildcard
        if "**" in pattern:
            prefix = pattern.replace("**", "")
            if capability.startswith(prefix):
                return True
        
        # Handle * wildcard
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(capability, pattern)
        
        return False
    
    def validate_tenant(self, tenant_id: str) -> bool:
        """Validate that this domain belongs to the specified tenant"""
        return self.tenant_id == tenant_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "domain_id": self.domain_id,
            "tenant_id": self.tenant_id,
            "capabilities": list(self.capabilities),
            "state_hash": self.state_hash or self.compute_state_hash(),
            "protocol_version": self.protocol_version,
            "created_at": self.created_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionDomain":
        """Create ExecutionDomain from dictionary"""
        return cls(
            domain_id=data["domain_id"],
            tenant_id=data["tenant_id"],
            capabilities=frozenset(data.get("capabilities", [])),
            state_hash=data.get("state_hash", ""),
            protocol_version=data.get("protocol_version", "1.0"),
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {})
        )
