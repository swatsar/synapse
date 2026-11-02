"""Autonomous optimization module.

Phase 10 - Production Autonomy & Self-Optimization.
"""
from .engine import AutonomousOptimizationEngine, OptimizationPlan, OptimizationResult
from .resource_manager import ResourceLimits, ResourceManager, ResourceUsage

__all__ = [
    "AutonomousOptimizationEngine",
    "OptimizationPlan",
    "OptimizationResult",
    "ResourceLimits",
    "ResourceManager",
    "ResourceUsage"
]
PROTOCOL_VERSION: str = "1.0"
