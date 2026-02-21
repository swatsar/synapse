PROTOCOL_VERSION: str = "1.0"
"""
Capability Revoker for revoking capabilities
"""

from synapse.governance.issuance import CapabilityIssuer

class CapabilityRevoker:
    """Revokes capabilities from agents"""
    
    def __init__(self, issuer: CapabilityIssuer):
        self.issuer = issuer
    
    def revoke(self, agent_id: str, capability_id: str):
        """Revoke a capability from an agent"""
        if agent_id in self.issuer._agent_capabilities and capability_id in self.issuer._agent_capabilities.get(agent_id, {}):
            del self.issuer._agent_capabilities[agent_id][capability_id]
