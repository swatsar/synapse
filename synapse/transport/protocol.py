PROTOCOL_VERSION: str = "1.0"
"""
Protocol definitions for orchestrator-node communication
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ProtocolVersion:
    """Protocol version information"""
    major: int
    minor: int
    patch: int
    
    @classmethod
    def from_string(cls, version_str: str) -> "ProtocolVersion":
        """Parse protocol version from string (e.g., "1.0" → (1, 0, 0))"""
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return cls(major, minor, patch)
    
    def __str__(self):
        """Convert to string format"""
        return f"{self.major}.{self.minor}.{self.patch}"
