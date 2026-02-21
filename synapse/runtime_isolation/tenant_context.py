"""
Tenant Context - Multi-tenant security context

TenantContext provides:
- Tenant identification
- Issued capabilities
- Execution quota tracking
"""

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Dict, Any
import fnmatch


@dataclass(frozen=True)
class TenantContext:
    """
    Immutable tenant context for multi-tenant security.
    
    Provides:
    - Tenant identification
    - Issued capabilities
    - Execution quota
    """
    tenant_id: str
    domain_id: str
    issued_capabilities: FrozenSet[str]
    execution_quota: int
    protocol_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate tenant context after initialization"""
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.domain_id:
            raise ValueError("domain_id is required")
    
    def has_capability(self, capability: str) -> bool:
        """
        Check if tenant has a specific capability.
        
        Supports wildcard matching.
        """
        for issued_cap in self.issued_capabilities:
            if self._match_capability(issued_cap, capability):
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
    
    def create_quota_tracker(self) -> "QuotaTracker":
        """Create a mutable quota tracker for this tenant"""
        return QuotaTracker(
            tenant_id=self.tenant_id,
            total_quota=self.execution_quota
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "tenant_id": self.tenant_id,
            "domain_id": self.domain_id,
            "issued_capabilities": list(self.issued_capabilities),
            "execution_quota": self.execution_quota,
            "protocol_version": self.protocol_version,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantContext":
        """Create TenantContext from dictionary"""
        return cls(
            tenant_id=data["tenant_id"],
            domain_id=data["domain_id"],
            issued_capabilities=frozenset(data.get("issued_capabilities", [])),
            execution_quota=data.get("execution_quota", 0),
            protocol_version=data.get("protocol_version", "1.0"),
            metadata=data.get("metadata", {})
        )


@dataclass
class QuotaTracker:
    """Mutable quota tracker for tenant execution"""
    tenant_id: str
    total_quota: int
    consumed: int = 0
    
    def consume(self, amount: int) -> int:
        """Consume quota. Raises error if exceeded."""
        if self.consumed + amount > self.total_quota:
            raise ValueError(
                f"Quota exceeded: trying to consume {amount}, "
                f"but only {self.remaining()} remaining"
            )
        self.consumed += amount
        return self.consumed
    
    def remaining(self) -> int:
        """Get remaining quota"""
        return self.total_quota - self.consumed
    
    def reset(self) -> None:
        """Reset consumed quota"""
        self.consumed = 0
