"""
Capability Policy Engine for validation
"""

from synapse.governance.capability_registry import CapabilityMetadata

class PolicyViolation(Exception):
    """Raised when a policy violation occurs"""
    pass

class CapabilityPolicyEngine:
    """Engine for validating capability usage"""
    
    def validate_capability(self, capability_id: str, metadata: CapabilityMetadata) -> bool:
        """Validate capability based on policy"""
        if metadata.risk_level > 3:
            return False
        return True
    
    def check_issuance_policy(self, agent_id: str, capability_id: str, metadata: CapabilityMetadata) -> bool:
        """Check if issuance policy allows capability to be issued"""
        if metadata.risk_level > 3:
            return False
        return True
