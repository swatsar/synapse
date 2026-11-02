"""Replication package – simple async data replication between nodes."""
from .manager import ReplicationManager

__all__ = ["ReplicationManager"]
PROTOCOL_VERSION: str = "1.0"
