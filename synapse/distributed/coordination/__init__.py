"""Coordination package – deterministic event ordering across nodes."""
from .service import ClusterCoordinationService

__all__ = ["ClusterCoordinationService"]
PROTOCOL_VERSION: str = "1.0"
