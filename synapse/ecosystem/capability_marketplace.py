"""
Capability Marketplace - Capability catalog & versioning
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib


PROTOCOL_VERSION: str = "1.0"


@dataclass
class CapabilityDescriptor:
    """Descriptor for a capability in the marketplace"""
    name: str
    version: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of capability"""
        content = f"{self.name}:{self.version}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()


class CapabilityMarketplace:
    """
    Marketplace for capabilities with versioning and dependency resolution.
    """
    
    def __init__(self):
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._versions: Dict[str, List[str]] = {}
        self.protocol_version: str = PROTOCOL_VERSION
    
    def register_capability(self, capability: Any) -> str:
        """Register a capability in the marketplace"""
        if hasattr(capability, 'name') and hasattr(capability, 'version'):
            key = f"{capability.name}:{capability.version}"
            desc = CapabilityDescriptor(
                name=capability.name,
                version=capability.version,
                description=getattr(capability, 'description', ''),
                dependencies=getattr(capability, 'dependencies', []),
                metadata=getattr(capability, 'metadata', {})
            )
            self._capabilities[key] = desc
            
            if capability.name not in self._versions:
                self._versions[capability.name] = []
            self._versions[capability.name].append(capability.version)
            
            return key
        return ""
    
    def list_capabilities(self, filter_name: str = None) -> List[CapabilityDescriptor]:
        """List all capabilities, optionally filtered by name"""
        if filter_name:
            return [c for c in self._capabilities.values() if c.name == filter_name]
        return list(self._capabilities.values())
    
    def get_capability(self, name: str, version: str = None) -> Optional[CapabilityDescriptor]:
        """Get a specific capability by name and optional version"""
        if version:
            key = f"{name}:{version}"
            return self._capabilities.get(key)
        
        # Get latest version
        if name in self._versions and self._versions[name]:
            latest_version = self._versions[name][-1]
            key = f"{name}:{latest_version}"
            return self._capabilities.get(key)
        
        return None
    
    def resolve_dependencies(self, capability_name: str) -> List[str]:
        """Resolve dependencies for a capability"""
        capability = self.get_capability(capability_name)
        if not capability:
            return []
        
        resolved = []
        for dep in capability.dependencies:
            if dep in self._capabilities:
                resolved.append(dep)
        
        return resolved
