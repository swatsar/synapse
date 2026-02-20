"""Isolation Enforcement Policy.

v3.1 Fix: Enforces isolation requirements based on trust and risk level.
"""
from enum import Enum

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class RuntimeIsolationType(str, Enum):
    """Runtime isolation types."""
    NONE = "none"
    SUBPROCESS = "subprocess"
    CONTAINER = "container"
    SANDBOX = "sandbox"


class IsolationEnforcementPolicy:
    """Enforces isolation requirements for skill execution.
    
    v3.1 Rules:
    - risk_level >= 3 → container minimum
    - unverified skill → container mandatory
    - trusted skill → subprocess allowed
    """
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
    
    def get_required_isolation(
        self,
        trust_level: str,
        risk_level: int
    ) -> RuntimeIsolationType:
        """Get required isolation type for trust/risk level.
        
        Args:
            trust_level: Trust level (trusted, verified, unverified)
            risk_level: Risk level 1-5
            
        Returns:
            Required RuntimeIsolationType
        """
        # v3.1 Rule: risk_level >= 3 always requires container
        if risk_level >= 3:
            return RuntimeIsolationType.CONTAINER
        
        # v3.1 Rule: unverified always requires container
        if trust_level == "unverified":
            return RuntimeIsolationType.CONTAINER
        
        # Trusted with low risk can use subprocess
        if trust_level == "trusted" and risk_level < 3:
            return RuntimeIsolationType.SUBPROCESS
        
        # Verified with medium risk
        if trust_level == "verified" and risk_level < 3:
            return RuntimeIsolationType.SUBPROCESS
        
        # Default to container for safety
        return RuntimeIsolationType.CONTAINER
