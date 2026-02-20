"""Autonomous optimization module.

Phase 10 - Production Autonomy & Self-Optimization.
"""
from .engine import (
    AutonomousOptimizationEngine,
    OptimizationPlan,
    OptimizationResult
)
from .resource_manager import (
    ResourceManager,
    ResourceLimits,
    ResourceUsage
)

__all__ = [
    "AutonomousOptimizationEngine",
    "OptimizationPlan",
    "OptimizationResult",
    "ResourceManager",
    "ResourceLimits",
    "ResourceUsage"
]
PROTOCOL_VERSION: str = "1.0"
