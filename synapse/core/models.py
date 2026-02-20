"""Core Models.

Pydantic models for the Synapse platform.
"""
from typing import Any, Dict, List, Optional, ClassVar
from pydantic import BaseModel, Field
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class ResourceLimits(BaseModel):
    """Resource limits for execution.
    
    v3.1 Fix: Strict schema with only allowed keys.
    """
    cpu_seconds: int = 60
    memory_mb: int = 512
    disk_mb: int = 100
    network_kb: int = 1024
    
    # Allow extra fields to be rejected
    model_config = {"extra": "forbid"}


class ExecutionContext(BaseModel):
    """Execution context for skill execution."""
    
    protocol_version: ClassVar[str] = "1.0"
    
    session_id: str
    agent_id: str
    trace_id: str
    capabilities: List[str] = Field(default_factory=list)
    memory_store: Any = None
    logger: Any = None
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    execution_seed: int = 42
    checkpoint_id: Optional[str] = None
    
    model_config = {"arbitrary_types_allowed": True}


class SkillManifest(BaseModel):
    """Manifest for a skill."""
    
    protocol_version: ClassVar[str] = "1.0"
    
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    inputs: Dict[str, str] = Field(default_factory=dict)
    outputs: Dict[str, str] = Field(default_factory=dict)
    required_capabilities: List[str] = Field(default_factory=list)
    risk_level: int = 1
    trust_level: str = "unverified"
    isolation_type: str = "subprocess"


class ActionPlan(BaseModel):
    """Plan for executing actions."""
    
    protocol_version: ClassVar[str] = "1.0"
    
    goal: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    risk_level: int = 1
    required_capabilities: List[str] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    """Entry in memory."""
    
    protocol_version: ClassVar[str] = "1.0"
    
    key: str
    value: Any
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    """Query for memory."""
    
    protocol_version: ClassVar[str] = "1.0"
    
    query_text: str
    limit: int = 10
    threshold: float = 0.7
    filters: Dict[str, Any] = Field(default_factory=dict)
