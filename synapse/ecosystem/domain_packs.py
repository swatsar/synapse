"""
Domain Packs - Pre-built agent configurations
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


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
    capabilities: List[str] = field(default_factory=list)
    agent_config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def validate(self) -> bool:
        """Validate domain pack configuration"""
        if not self.name:
            return False
        if not self.version:
            return False
        if not self.description:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
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
