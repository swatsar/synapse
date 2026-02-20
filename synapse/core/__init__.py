PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
"""Core package public API.

The original ``__init__`` re‑exported :class:`Orchestrator`.  This caused a
circular import because ``ExecutionGuard`` (used by the new environment
implementations) imports :class:`ResourceLimits` from ``synapse.core.models``
andand ``Orchestrator`` itself imports ``ExecutionGuard``.  Importing
``Orchestrator`` here therefore created the chain:

``synapse.core`` → ``Orchestrator`` → ``ExecutionGuard`` → ``ResourceLimits``
→ ``synapse.core`` (again).

To resolve the issue we now only expose the data models from this package.
Agents that need ``Orchestrator`` should import it directly:

    from synapse.core.orchestrator import Orchestrator

This keeps the public interface clean and eliminates the circular import.
"""

# Export only the models (typing, dataclasses, etc.)
from .models import *  # noqa: F401,F403

# ``__all__`` will be populated by the star‑import above.
__all__ = []
