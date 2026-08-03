"""
Capability Governance Module
"""

from synapse.governance.capability_policy import CapabilityPolicyEngine, PolicyViolation
from synapse.governance.capability_registry import (
    CapabilityMetadata,
    CapabilityRegistry,
)
from synapse.governance.issuance import CapabilityIssuer
from synapse.governance.revocation import CapabilityRevoker

__all__ = [
    'CapabilityIssuer',
    'CapabilityMetadata',
    'CapabilityPolicyEngine',
    'CapabilityRegistry',
    'CapabilityRevoker',
    'PolicyViolation'
]
