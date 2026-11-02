"""Compatibility shim for the LLM router.

Historically this module held a second, near-identical copy of
LLMRouter/LLMPriority (duplicating synapse.llm.provider). That duplicate
implementation was removed to keep a single source of truth for the LLM
provider layer. This module now re-exports the canonical names so existing
imports keep working, and emits a DeprecationWarning on use.

Import from synapse.llm.provider instead.
"""
import warnings

from synapse.llm.provider import (  # noqa: F401  (re-exported for compat)
    EmbeddingUnavailable,
    LLMPriority,
    LiteLLMProvider,
    LLMRouter,
    PROTOCOL_VERSION,
    create_default_router,
)

__all__ = [
    "EmbeddingUnavailable",
    "LLMPriority",
    "LiteLLMProvider",
    "LLMRouter",
    "PROTOCOL_VERSION",
    "create_default_router",
]

warnings.warn(
    "synapse.llm.router is deprecated; import from synapse.llm.provider instead",
    DeprecationWarning,
    stacklevel=2,
)
