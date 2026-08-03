PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

"""Synapse agents module."""
from .critic import CriticAgent
from .developer import DeveloperAgent
from .optimizer import OptimizationRequest, OptimizationResponse, OptimizerAgent

__all__ = [
    "CriticAgent",
    "DeveloperAgent",
    "OptimizationRequest",
    "OptimizationResponse",
    "OptimizerAgent"
]
