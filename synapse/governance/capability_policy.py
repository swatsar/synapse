"""
Capability Policy Engine for validation.

Protocol Version: 1.0
Specification: 3.1
"""

PROTOCOL_VERSION: str = "1.0"

from synapse.governance.capability_registry import CapabilityMetadata


class PolicyViolation(Exception):
    """Raised when a policy violation occurs"""

class CapabilityPolicyEngine:
    """Engine for validating capability usage"""
    
    def validate_capability(self, capability_id: str, metadata: CapabilityMetadata) -> bool:
        """Validate capability based on policy"""
        return not metadata.risk_level > 3
    
    def check_issuance_policy(self, agent_id: str, capability_id: str, metadata: CapabilityMetadata) -> bool:
        """Check if issuance policy allows capability to be issued"""
        return not metadata.risk_level > 3
