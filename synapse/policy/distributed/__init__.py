PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

"""Distributed policy package – extends core PolicyEngine with federation checks."""
from .engine import DistributedPolicyEngine

__all__ = ["DistributedPolicyEngine"]
