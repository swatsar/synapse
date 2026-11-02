"""Core package public API.

The original ``__init__`` re-exported :class:`Orchestrator`.  This caused a
circular import because ``ExecutionGuard`` (used by the new environment
implementations) imports :class:`ResourceLimits` from ``synapse.core.models``
and ``Orchestrator`` itself imports ``ExecutionGuard``.  Importing
``Orchestrator`` here therefore created the chain:

``synapse.core`` -> ``Orchestrator`` -> ``ExecutionGuard`` -> ``ResourceLimits``
-> ``synapse.core`` (again).

To resolve the issue we now only expose the data models from this package.
Agents that need ``Orchestrator`` should import it directly:

    from synapse.core.orchestrator import Orchestrator

This keeps the public interface clean and eliminates the circular import.
"""

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Export only the models (typing, dataclasses, etc.)
# Explicit exports to avoid wildcard import
from .models import (
    ResourceLimits,
    ExecutionContext,
    SkillManifest,
    ActionPlan,
    MemoryEntry,
    MemoryQuery,
)

__all__ = [
    "PROTOCOL_VERSION",
    "SPEC_VERSION",
    "ResourceLimits",
    "ExecutionContext",
    "SkillManifest",
    "ActionPlan",
    "MemoryEntry",
    "MemoryQuery",
]
