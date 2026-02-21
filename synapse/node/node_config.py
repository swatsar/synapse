"""
Node Configuration
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class NodeConfig:
    """Node configuration"""
    node_id: str = "local_node"
    port: int = 8080
    host: str = "localhost"
    max_concurrent_workflows: int = 10
    execution_timeout_seconds: int = 300
    protocol_version: str = "1.0"
    environment: str = "production"
    capabilities: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = {}
