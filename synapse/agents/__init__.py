PROTOCOL_VERSION: str = "1.0"
"""Synapse agents module."""
from .developer import DeveloperAgent
from .critic import CriticAgent
from .optimizer import OptimizerAgent, OptimizationRequest, OptimizationResponse

__all__ = [
    "DeveloperAgent",
    "CriticAgent",
    "OptimizerAgent",
    "OptimizationRequest",
    "OptimizationResponse"
]
