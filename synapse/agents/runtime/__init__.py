PROTOCOL_VERSION: str = "1.0"
"""Runtime agents package.

The original codebase used a class named ``RuntimeAgent``.  The current
implementation provides ``CognitiveAgent`` in ``synapse.agents.runtime.agent``.
For backward compatibility we import that class and expose it under the
expected name.
"""

from .agent import CognitiveAgent as RuntimeAgent

__all__ = ["RuntimeAgent"]
