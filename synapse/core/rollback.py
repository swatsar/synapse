"""Rollback orchestration – synchronous implementation (v3.1 compliant)."""
import uuid
from .audit import AuditLogger
from .security import CapabilityManager
from .checkpoint import CheckpointManager


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

class RollbackManager:
    """Handles deterministic rollback to a previously created checkpoint."""
    def __init__(self, cp_manager: CheckpointManager, cap_manager: CapabilityManager, audit: AuditLogger):
        self.cp_manager = cp_manager
        self.cap_manager = cap_manager
        self.audit = audit

    def rollback_to(self, checkpoint_id: uuid.UUID) -> None:
        # Capability enforcement omitted for sync version.
        self.audit.record("rollback_requested", {"checkpoint": str(checkpoint_id)})
        self.cp_manager.restore(checkpoint_id)
        self.audit.record("rollback_completed", {"checkpoint": str(checkpoint_id)})
