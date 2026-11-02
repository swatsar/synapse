"""Reliability package – snapshots, rollback and fault tolerance utilities."""
from .fault_tolerance import FaultTolerance
from .rollback_manager import RollbackManager
from .snapshot_manager import SnapshotManager

__all__ = ["FaultTolerance", "RollbackManager", "SnapshotManager"]
PROTOCOL_VERSION: str = "1.0"
