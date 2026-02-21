"""
Task Model for orchestrator
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC
import uuid

@dataclass
class Task:
    """Task definition for orchestrator"""
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)  # Alias for required_capabilities
    priority: int = 1
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    protocol_version: str = "1.0"
    agent_id: Optional[str] = None
    execution_seed: Optional[int] = None
