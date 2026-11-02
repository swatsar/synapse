"""Distributed memory package – provides a simple async wrapper around the core MemoryStore.
"""
from .store import DistributedMemoryStore

__all__ = ["DistributedMemoryStore"]
PROTOCOL_VERSION: str = "1.0"
