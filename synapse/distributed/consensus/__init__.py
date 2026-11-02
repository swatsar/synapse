"""Consensus package – deterministic state agreement across nodes (simple leader election)."""
from .engine import ConsensusEngine

__all__ = ["ConsensusEngine"]
PROTOCOL_VERSION: str = "1.0"
