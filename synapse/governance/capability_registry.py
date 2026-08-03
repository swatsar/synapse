"""
Capability Registry for managing capabilities
"""

PROTOCOL_VERSION: str = "1.0"

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CapabilityMetadata:
    """Metadata for a capability"""
    name: str
    description: str
    category: str
    risk_level: int
    protocol_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

class CapabilityRegistry:
    """Registry for managing capabilities"""
    
    def __init__(self):
        self._capabilities: dict[str, CapabilityMetadata] = {}
    
    def register(self, capability_id: str, metadata: CapabilityMetadata):
        """Register a new capability"""
        if capability_id in self._capabilities:
            raise ValueError(f"Capability already registered: {capability_id}")
        
        self._capabilities[capability_id] = metadata
    
    def get_metadata(self, capability_id: str) -> CapabilityMetadata | None:
        """Get metadata for a capability"""
        return self._capabilities.get(capability_id)
    
    def list_capabilities(self) -> list[str]:
        """List all registered capabilities"""
        return list(self._capabilities.keys())
    
    def unregister(self, capability_id: str):
        """Unregister a capability"""
        if capability_id in self._capabilities:
            del self._capabilities[capability_id]
