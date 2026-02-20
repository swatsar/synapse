"""Checkpoint System.

Provides checkpoint creation and state management for rollback.
"""
import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, ClassVar
from pydantic import BaseModel, Field

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class Checkpoint(BaseModel):
    """Checkpoint for state capture and rollback.
    
    v3.1 Fix: Uses is_active column, is_fresh() method (no ORM conflict).
    v3.1 Addition: security_hash for integrity verification.
    """
    
    # Class-level protocol version (for hasattr check)
    protocol_version: ClassVar[str] = "1.0"
    
    # Instance fields
    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = "default"
    session_id: str = "default"
    state: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    is_active: bool = True
    security_hash: str = ""  # v3.1: Security hash for integrity verification
    _instance_protocol_version: str = "1.0"
    _original_state: Dict[str, Any] = None  # Store original state for rollback
    
    def __init__(self, **data):
        super().__init__(**data)
        self._instance_protocol_version = "1.0"
        # Generate security hash if not provided
        if not self.security_hash and self.state:
            self.security_hash = self._compute_hash(self.state)
    
    def _compute_hash(self, state: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of state for integrity verification."""
        state_json = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    @property
    def id(self) -> uuid.UUID:
        """Get checkpoint ID as UUID."""
        return uuid.UUID(self.checkpoint_id)
    
    def is_fresh(self, max_age_seconds: float = 3600.0) -> bool:
        """Check if checkpoint is fresh (not too old).
        
        Args:
            max_age_seconds: Maximum age in seconds
            
        Returns:
            True if checkpoint is fresh
        """
        now = datetime.now(timezone.utc).timestamp()
        return (now - self.created_at) < max_age_seconds
    
    def verify_integrity(self) -> bool:
        """Verify checkpoint integrity using security hash.
        
        Returns:
            True if integrity is valid
        """
        if not self.security_hash:
            return True  # No hash to verify
        expected_hash = self._compute_hash(self.state)
        return self.security_hash == expected_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "checkpoint_id": self.checkpoint_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "state": self.state,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "security_hash": self.security_hash,
            "protocol_version": self._instance_protocol_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Create checkpoint from dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            Checkpoint instance
        """
        return cls(**data)


class CheckpointManager:
    """Manager for creating, storing, and restoring checkpoints.
    
    v3.1 Compliant: Uses is_active/is_fresh pattern.
    v3.1 Addition: Security hash generation.
    """
    
    protocol_version: ClassVar[str] = "1.0"
    
    def __init__(self, cap_manager=None, audit=None):
        """Initialize checkpoint manager.
        
        Args:
            cap_manager: Capability manager for permission checks
            audit: Audit logger for recording operations
        """
        self.cap_manager = cap_manager
        self.audit = audit
        self._checkpoints: Dict[str, Checkpoint] = {}
    
    def create_checkpoint(
        self,
        state: Dict[str, Any],
        agent_id: str = "default",
        session_id: str = "default"
    ) -> Checkpoint:
        """Create a new checkpoint.
        
        Args:
            state: State to checkpoint
            agent_id: Agent ID
            session_id: Session ID
            
        Returns:
            Created checkpoint
        """
        import copy
        checkpoint = Checkpoint(
            state=copy.deepcopy(state),
            agent_id=agent_id,
            session_id=session_id
        )
        # Store original state for rollback
        checkpoint._original_state = copy.deepcopy(state)
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        
        if self.audit:
            self.audit.record("checkpoint_created", {
                "checkpoint_id": checkpoint.checkpoint_id,
                "agent_id": agent_id,
                "security_hash": checkpoint.security_hash[:16] + "..."  # Partial hash for audit
            })
        
        return checkpoint
    
    def get_checkpoint(self, checkpoint_id: uuid.UUID) -> Optional[Checkpoint]:
        """Get checkpoint by ID.
        
        Args:
            checkpoint_id: Checkpoint UUID
            
        Returns:
            Checkpoint if found, None otherwise
        """
        return self._checkpoints.get(str(checkpoint_id))
    
    def get_state(self, checkpoint_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get state from checkpoint.
        
        Args:
            checkpoint_id: Checkpoint UUID
            
        Returns:
            State dict if found, None otherwise
        """
        cp = self.get_checkpoint(checkpoint_id)
        return cp.state if cp else None
    
    def update_state(self, checkpoint_id: uuid.UUID, state: Dict[str, Any]) -> bool:
        """Update checkpoint state.
        
        Args:
            checkpoint_id: Checkpoint UUID
            state: New state
            
        Returns:
            True if updated, False if not found
        """
        cp = self.get_checkpoint(checkpoint_id)
        if cp:
            cp.state = state
            cp.security_hash = cp._compute_hash(state)  # Update hash
            if self.audit:
                self.audit.record("checkpoint_updated", {
                    "checkpoint_id": str(checkpoint_id)
                })
            return True
        return False
    
    def restore(self, checkpoint_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoint to original.
        
        Args:
            checkpoint_id: Checkpoint UUID
            
        Returns:
            Restored state if found, None otherwise
        """
        import copy
        cp = self.get_checkpoint(checkpoint_id)
        if cp and cp.is_active:
            # Verify integrity before restore
            if not cp.verify_integrity():
                if self.audit:
                    self.audit.record("checkpoint_integrity_failed", {
                        "checkpoint_id": str(checkpoint_id)
                    })
                return None
            
            # Restore original state
            if cp._original_state is not None:
                cp.state = copy.deepcopy(cp._original_state)
            if self.audit:
                self.audit.record("checkpoint_restored", {
                    "checkpoint_id": str(checkpoint_id)
                })
            return cp.state
        return None
    
    def delete_checkpoint(self, checkpoint_id: uuid.UUID) -> bool:
        """Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint UUID
            
        Returns:
            True if deleted, False if not found
        """
        key = str(checkpoint_id)
        if key in self._checkpoints:
            del self._checkpoints[key]
            if self.audit:
                self.audit.record("checkpoint_deleted", {
                    "checkpoint_id": str(checkpoint_id)
                })
            return True
        return False
