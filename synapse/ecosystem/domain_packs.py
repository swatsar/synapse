"""
Domain Packs - Pre-built agent configurations
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PROTOCOL_VERSION: str = "1.0"


@dataclass
class DomainPack:
    """
    Pre-built agent configuration pack.
    
    Domain packs provide pre-configured agent setups for specific domains.
    """
    name: str
    version: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    agent_config: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    
    def validate(self) -> bool:
        """Validate domain pack configuration"""
        if not self.name:
            return False
        if not self.version:
            return False
        return self.description
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'capabilities': self.capabilities,
            'agent_config': self.agent_config,
            'dependencies': self.dependencies,
            'metadata': self.metadata,
            'protocol_version': self.protocol_version,
            'created_at': self.created_at
        }
