PROTOCOL_VERSION: str = "1.0"
"""Distributed policy package – extends core PolicyEngine with federation checks."""
from .engine import DistributedPolicyEngine

__all__ = ["DistributedPolicyEngine"]
