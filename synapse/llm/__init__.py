PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
"""LLM Provider Layer."""
from .provider import LLMRouter

__all__ = ["LLMRouter"]
