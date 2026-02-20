"""Cluster runtime – orchestrates multiple node runtimes and coordinates snapshots/rollbacks."""
from .manager import ClusterManager

__all__ = ["ClusterManager"]
PROTOCOL_VERSION: str = "1.0"
