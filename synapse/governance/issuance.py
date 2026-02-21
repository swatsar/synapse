"""
Capability Issuer for issuing capabilities to agents
"""

from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from synapse.governance.capability_registry import CapabilityRegistry, CapabilityMetadata
from synapse.governance.capability_policy import CapabilityPolicyEngine, PolicyViolation

class CapabilityIssuer:
    """Issues capabilities to agents"""
    
    def __init__(self, registry: CapabilityRegistry, policy_engine: Optional[CapabilityPolicyEngine] = None):
        self.registry = registry
        self.policy_engine = policy_engine or CapabilityPolicyEngine()
        self._agent_capabilities: Dict[str, Dict[str, datetime]] = {}
    
    def issue(self, agent_id: str, capability_id: str, expires_at: Optional[datetime] = None):
        """Issue a capability to an agent"""
        metadata = self.registry.get_metadata(capability_id)
        if not metadata:
            raise ValueError(f"Capability not registered: {capability_id}")
        
        if not self.policy_engine.check_issuance_policy(agent_id, capability_id, metadata):
            raise PolicyViolation(f"Issuance policy violation for {capability_id}")
        
        if agent_id not in self._agent_capabilities:
            self._agent_capabilities[agent_id] = {}
        
        if expires_at is None:
            expires_at = datetime.now() + timedelta(days=365)
        
        self._agent_capabilities[agent_id][capability_id] = expires_at
    
    def has_capability(self, agent_id: str, capability_id: str) -> bool:
        """Check if agent has capability"""
        if agent_id not in self._agent_capabilities:
            return False
        
        if capability_id not in self._agent_capabilities[agent_id]:
            return False
        
        expires_at = self._agent_capabilities[agent_id][capability_id]
        return datetime.now() < expires_at
    
    def validate(self, agent_id: str, capability_id: str) -> bool:
        """Validate capability for agent"""
        return self.has_capability(agent_id, capability_id)
    
    def get_agent_capabilities(self, agent_id: str) -> Set[str]:
        """Get all active capabilities for an agent"""
        if agent_id not in self._agent_capabilities:
            return set()
        
        now = datetime.now()
        active = []
        for capability, expires_at in self._agent_capabilities[agent_id].items():
            if now < expires_at:
                active.append(capability)
        
        return set(active)
