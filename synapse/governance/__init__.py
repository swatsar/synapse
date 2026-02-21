"""
Capability Governance Module
"""

from synapse.governance.capability_registry import CapabilityRegistry, CapabilityMetadata
from synapse.governance.capability_policy import CapabilityPolicyEngine, PolicyViolation
from synapse.governance.issuance import CapabilityIssuer
from synapse.governance.revocation import CapabilityRevoker

__all__ = [
    'CapabilityRegistry',
    'CapabilityMetadata', 
    'CapabilityPolicyEngine',
    'PolicyViolation',
    'CapabilityIssuer',
    'CapabilityRevoker'
]
