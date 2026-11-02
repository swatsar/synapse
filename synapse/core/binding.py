"""
Binding Manager for agent-capability bindings
"""

PROTOCOL_VERSION: str = "1.0"

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AgentCapabilityBinding:
    """Binding between agent and capabilities"""
    # Required fields first (no defaults)
    agent_id: str
    capabilities: list[str]
    # Optional fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    protocol_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

class BindingManager:
    """Manages agent-capability bindings"""
    
    def __init__(self):
        self._bindings: dict[str, AgentCapabilityBinding] = {}
    
    def _normalize_capabilities(self, capabilities: str | list[str]) -> list[str]:
        """Convert single capability string to list"""
        if isinstance(capabilities, str):
            return [capabilities]
        return list(capabilities)
    
    def create_binding(self, agent_id: str, capabilities: str | list[str]) -> str:
        """Create a new binding and return binding ID (string)"""
        caps_list = self._normalize_capabilities(capabilities)
        binding = AgentCapabilityBinding(
            agent_id=agent_id,
            capabilities=caps_list
        )
        self._bindings[binding.id] = binding
        return binding.id  # Return the ID string
    
    def bind(self, agent_id: str, capabilities: str | list[str]) -> str:
        """Alias for create_binding - returns binding ID string"""
        return self.create_binding(agent_id, capabilities)
    
    def get_binding(self, binding_id: str) -> AgentCapabilityBinding | None:
        """Get binding by ID"""
        return self._bindings.get(binding_id)
    
    def get_agent_bindings(self, agent_id: str) -> list[AgentCapabilityBinding]:
        """Get all bindings for an agent"""
        return [b for b in self._bindings.values() if b.agent_id == agent_id]
    
    def get_agent_capabilities(self, agent_id: str) -> list[str]:
        """Get all capabilities for an agent"""
        capabilities = set()
        for binding in self.get_agent_bindings(agent_id):
            capabilities.update(binding.capabilities)
        return list(capabilities)
    
    def check_binding(self, agent_id: str, capability: str) -> bool:
        """Check if agent has a specific capability"""
        return capability in self.get_agent_capabilities(agent_id)
    
    def unbind(self, agent_id: str, capability: str) -> bool:
        """Remove a specific capability from agent's bindings"""
        for binding in self.get_agent_bindings(agent_id):
            if capability in binding.capabilities:
                binding.capabilities.remove(capability)
                return True
        return False
    
    def has_binding(self, agent_id: str, capability: str) -> bool:
        """Check if agent has a specific capability binding"""
        return self.check_binding(agent_id, capability)
    
    def check_capabilities(self, required: list[str], context) -> Any:
        """Check if required capabilities are available"""
        from dataclasses import dataclass
        
        @dataclass
        class SecurityCheckResult:
            approved: bool
            blocked_capabilities: list[str]
            required_approval: bool
            protocol_version: str = "1.0"
        
        agent_caps = set(self.get_agent_capabilities(context.agent_id))
        required_set = set(required)
        missing = required_set - agent_caps
        
        return SecurityCheckResult(
            approved=len(missing) == 0,
            blocked_capabilities=list(missing),
            required_approval=len(missing) > 0
        )
