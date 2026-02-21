"""
Capability Domain - Capability scope boundaries

CapabilityDomain limits the scope of capabilities and prevents:
- Capability reuse between tenants
- Capability escalation across domain
"""

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Dict, Any, Set
import fnmatch


@dataclass
class CapabilityDomain:
    """
    Capability domain that defines capability scope boundaries.
    
    Prevents:
    - Capability reuse between tenants
    - Capability escalation across domain
    """
    domain_id: str
    allowed_capabilities: FrozenSet[str]
    tenant_id: Optional[str] = None
    protocol_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate capability domain after initialization"""
        if not self.domain_id:
            raise ValueError("domain_id is required")
    
    def validate_capability_scope(self, capability: str) -> bool:
        """
        Validate if a capability is within this domain's scope.
        
        Supports wildcard matching:
        - "fs:read:/workspace/**" matches "fs:read:/workspace/file.txt"
        """
        for allowed_cap in self.allowed_capabilities:
            if self._match_capability(allowed_cap, capability):
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
            return fnmatch.fnmatch(capability, pattern)
        
        return False
    
    def can_escalate_to(self, target_capability: str) -> bool:
        """
        Check if capability can be escalated to target.
        
        By default, escalation is NOT allowed.
        """
        # Escalation is never allowed by default
        return False
    
    def is_within_boundary(self, capability: str) -> bool:
        """
        Check if capability is within domain boundary.
        
        This is an alias for validate_capability_scope.
        """
        return self.validate_capability_scope(capability)
    
    def get_capabilities_for_tenant(self, tenant_id: str) -> FrozenSet[str]:
        """Get capabilities for a specific tenant"""
        if self.tenant_id and self.tenant_id != tenant_id:
            return frozenset()  # No capabilities for different tenant
        return self.allowed_capabilities
    
    def validate_tenant_access(self, tenant_id: str) -> bool:
        """Validate that tenant has access to this domain"""
        if self.tenant_id is None:
            return True  # No tenant restriction
        return self.tenant_id == tenant_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "domain_id": self.domain_id,
            "allowed_capabilities": list(self.allowed_capabilities),
            "tenant_id": self.tenant_id,
            "protocol_version": self.protocol_version,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityDomain":
        """Create CapabilityDomain from dictionary"""
        return cls(
            domain_id=data["domain_id"],
            allowed_capabilities=frozenset(data.get("allowed_capabilities", [])),
            tenant_id=data.get("tenant_id"),
            protocol_version=data.get("protocol_version", "1.0"),
            metadata=data.get("metadata", {})
        )
