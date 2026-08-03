"""
Task Model for orchestrator
"""

PROTOCOL_VERSION: str = "1.0"

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Task:
    """Task definition for orchestrator"""
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)  # Alias for required_capabilities
    priority: int = 1
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    protocol_version: str = "1.0"
    agent_id: str | None = None
    execution_seed: int | None = None
