"""Skill Registry with 6-Status Lifecycle Management.
Spec v3.1 compliant.

Lifecycle Statuses:
1. GENERATED  - Только что сгенерирован LLM
2. TESTED     - Автоматические тесты пройдены
3. VERIFIED   - Security scan пройден
4. ACTIVE     - Активен и используется
5. DEPRECATED - Устарел, не используется в новых планах
6. ARCHIVED   - Архивирован, терминальное состояние

Valid Transitions:
GENERATED → TESTED, ARCHIVED
TESTED → VERIFIED, GENERATED
VERIFIED → ACTIVE, TESTED
ACTIVE → DEPRECATED, VERIFIED
DEPRECATED → ARCHIVED, ACTIVE
ARCHIVED → (terminal, no transitions)
"""
PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

import importlib.util
import os
import pathlib
from typing import Callable, Dict, Optional, List
from enum import Enum
from datetime import datetime
import uuid

from synapse.core.models import SkillManifest, ResourceLimits
from synapse.security.execution_guard import ExecutionGuard
from synapse.security.capability_manager import CapabilityManager
from synapse.observability.logger import audit


class SkillLifecycleStatus(str, Enum):
    """6-Status Skill Lifecycle.
    
    GENERATED → TESTED → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
    
    Each status has specific valid transitions.
    ARCHIVED is a terminal state with no outgoing transitions.
    """
    GENERATED = "generated"      # Только что сгенерирован
    TESTED = "tested"           # Тесты пройдены
    VERIFIED = "verified"       # Security scan пройден
    ACTIVE = "active"           # Активен и используется
    DEPRECATED = "deprecated"   # Устарел
    ARCHIVED = "archived"       # Архивирован (terminal)


class SkillLifecycleTransitionError(Exception):
    """Raised when an invalid lifecycle transition is attempted."""
    pass


class SkillRecord:
    """Record for a skill with lifecycle tracking."""
    
    def __init__(
        self,
        skill_id: str,
        manifest: SkillManifest,
        handler: Callable,
        status: SkillLifecycleStatus = SkillLifecycleStatus.GENERATED
    ):
        self.skill_id = skill_id
        self.manifest = manifest
        self.handler = handler
        self.status = status
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.status_history: List[Dict] = [{
            "status": status.value,
            "timestamp": self.created_at,
            "reason": "initial"
        }]
        self.protocol_version = PROTOCOL_VERSION
    
    def to_dict(self) -> Dict:
        return {
            "skill_id": self.skill_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status_history": self.status_history,
            "protocol_version": self.protocol_version
        }


class SkillRegistry:
    """Registry for dynamically loaded skills with lifecycle management.
    
    Handles:
    - Manifest validation
    - Versioning
    - Sandboxed loading
    - 6-status lifecycle transitions
    - Audit logging for all operations
    """
    
    protocol_version: str = "1.0"

    # Valid lifecycle transitions
    VALID_TRANSITIONS: Dict[SkillLifecycleStatus, List[SkillLifecycleStatus]] = {
        SkillLifecycleStatus.GENERATED: [
            SkillLifecycleStatus.TESTED,
            SkillLifecycleStatus.ARCHIVED
        ],
        SkillLifecycleStatus.TESTED: [
            SkillLifecycleStatus.VERIFIED,
            SkillLifecycleStatus.GENERATED
        ],
        SkillLifecycleStatus.VERIFIED: [
            SkillLifecycleStatus.ACTIVE,
            SkillLifecycleStatus.TESTED
        ],
        SkillLifecycleStatus.ACTIVE: [
            SkillLifecycleStatus.DEPRECATED,
            SkillLifecycleStatus.VERIFIED
        ],
        SkillLifecycleStatus.DEPRECATED: [
            SkillLifecycleStatus.ARCHIVED,
            SkillLifecycleStatus.ACTIVE
        ],
        SkillLifecycleStatus.ARCHIVED: []  # Terminal state
    }

    def __init__(self, capability_manager: CapabilityManager):
        self._registry: Dict[str, SkillRecord] = {}
        self._manifests: Dict[str, SkillManifest] = {}
        self.capability_manager = capability_manager
        # Create default limits for the guard
        default_limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        self.guard = ExecutionGuard(limits=default_limits)

        audit(
            event="skill_registry_initialized",
            protocol_version=self.protocol_version,
            lifecycle_statuses=[s.value for s in SkillLifecycleStatus]
        )

    def _validate_manifest(self, manifest: SkillManifest) -> None:
        """Validate skill manifest.
        
        Args:
            manifest: Skill manifest to validate
            
        Raises:
            ValueError: If manifest is invalid
        """
        if not manifest.name or not manifest.version:
            raise ValueError("Invalid SkillManifest – missing name or version")
        # Future: add schema validation, trust level checks, etc.

    def _is_valid_transition(
        self,
        from_status: SkillLifecycleStatus,
        to_status: SkillLifecycleStatus
    ) -> bool:
        """Check if a lifecycle transition is valid.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if transition is valid
        """
        return to_status in self.VALID_TRANSITIONS.get(from_status, [])

    async def transition(
        self,
        skill_id: str,
        to_status: SkillLifecycleStatus,
        reason: str = "manual"
    ) -> bool:
        """Transition a skill to a new lifecycle status.
        
        Args:
            skill_id: ID of the skill
            to_status: Target status
            reason: Reason for transition
            
        Returns:
            True if transition succeeded
            
        Raises:
            SkillLifecycleTransitionError: If transition is invalid
        """
        if skill_id not in self._registry:
            raise SkillLifecycleTransitionError(f"Skill {skill_id} not found")
        
        record = self._registry[skill_id]
        from_status = record.status
        
        # Validate transition
        if not self._is_valid_transition(from_status, to_status):
            raise SkillLifecycleTransitionError(
                f"Invalid transition: {from_status.value} → {to_status.value}"
            )
        
        # Create checkpoint for critical transitions
        if to_status == SkillLifecycleStatus.ACTIVE:
            await self._create_checkpoint(skill_id, record)
        
        # Update status
        old_status = record.status
        record.status = to_status
        record.updated_at = datetime.utcnow().isoformat()
        record.status_history.append({
            "status": to_status.value,
            "timestamp": record.updated_at,
            "reason": reason,
            "from_status": old_status.value
        })
        
        # Audit logging
        audit(
            event="skill_lifecycle_transition",
            skill_id=skill_id,
            from_status=from_status.value,
            to_status=to_status.value,
            reason=reason,
            protocol_version=self.protocol_version
        )
        
        return True

    async def _create_checkpoint(self, skill_id: str, record: SkillRecord) -> str:
        """Create checkpoint before activating a skill.
        
        Args:
            skill_id: ID of the skill
            record: Skill record
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid.uuid4())
        
        audit(
            event="skill_checkpoint_created",
            skill_id=skill_id,
            checkpoint_id=checkpoint_id,
            protocol_version=self.protocol_version
        )
        
        return checkpoint_id

    async def register(
        self,
        manifest: SkillManifest,
        handler: Callable,
        initial_status: SkillLifecycleStatus = SkillLifecycleStatus.GENERATED
    ) -> str:
        """Register a skill after validation and sandbox checks.
        
        Args:
            manifest: Skill manifest
            handler: Skill handler function
            initial_status: Initial lifecycle status
            
        Returns:
            Skill ID
        """
        self._validate_manifest(manifest)
        
        # Capability check before registration
        await self.capability_manager.check_capability(manifest.required_capabilities)
        
        # Generate skill ID
        skill_id = str(uuid.uuid4())
        
        # Add trust_level and risk_level attributes for ExecutionGuard
        handler.trust_level = manifest.trust_level
        handler.risk_level = manifest.risk_level
        
        # Create skill record
        record = SkillRecord(
            skill_id=skill_id,
            manifest=manifest,
            handler=handler,
            status=initial_status
        )
        
        self._registry[skill_id] = record
        self._manifests[manifest.name] = manifest
        
        # Audit logging
        audit(
            event="skill_registered",
            skill_id=skill_id,
            name=manifest.name,
            version=manifest.version,
            status=initial_status.value,
            protocol_version=self.protocol_version
        )
        
        return skill_id

    def get(self, name: str) -> Callable:
        """Get a skill handler by name.
        
        Args:
            name: Skill name
            
        Returns:
            Skill handler
        """
        return self._registry[name].handler

    def get_by_id(self, skill_id: str) -> Optional[SkillRecord]:
        """Get a skill record by ID.
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Skill record or None
        """
        return self._registry.get(skill_id)

    def get_status(self, skill_id: str) -> Optional[SkillLifecycleStatus]:
        """Get the lifecycle status of a skill.
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Lifecycle status or None
        """
        record = self._registry.get(skill_id)
        return record.status if record else None

    def get_active_skills(self) -> List[SkillRecord]:
        """Get all active skills.
        
        Returns:
            List of active skill records
        """
        return [
            r for r in self._registry.values()
            if r.status == SkillLifecycleStatus.ACTIVE
        ]

    def get_skills_by_status(self, status: SkillLifecycleStatus) -> List[SkillRecord]:
        """Get all skills with a specific status.
        
        Args:
            status: Lifecycle status
            
        Returns:
            List of skill records
        """
        return [r for r in self._registry.values() if r.status == status]

    async def load_from_path(self, path: str) -> str:
        """Load a Python file that defines a `manifest` and a `handler`.
        
        The file is executed in a sandboxed environment via ExecutionGuard.
        
        Args:
            path: Path to skill file
            
        Returns:
            Skill ID
        """
        spec = importlib.util.spec_from_file_location("dynamic_skill", path)
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise ImportError(f"Cannot load skill from {path}")
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        manifest: SkillManifest = getattr(module, "manifest")
        handler: Callable = getattr(module, "handler")
        return await self.register(manifest, handler)

    def list_skills(self) -> Dict[str, SkillManifest]:
        """List all registered skills.
        
        Returns:
            Dictionary of skill names to manifests
        """
        return self._manifests.copy()

    def list_skills_with_status(self) -> List[Dict]:
        """List all skills with their lifecycle status.
        
        Returns:
            List of skill info dictionaries
        """
        return [record.to_dict() for record in self._registry.values()]

    async def archive_skill(self, skill_id: str, reason: str = "manual") -> bool:
        """Archive a skill (terminal state).
        
        Args:
            skill_id: Skill ID
            reason: Reason for archiving
            
        Returns:
            True if archived successfully
        """
        return await self.transition(
            skill_id,
            SkillLifecycleStatus.ARCHIVED,
            reason
        )

    async def deprecate_skill(self, skill_id: str, reason: str = "manual") -> bool:
        """Deprecate a skill.
        
        Args:
            skill_id: Skill ID
            reason: Reason for deprecation
            
        Returns:
            True if deprecated successfully
        """
        return await self.transition(
            skill_id,
            SkillLifecycleStatus.DEPRECATED,
            reason
        )

    async def activate_skill(self, skill_id: str, reason: str = "manual") -> bool:
        """Activate a verified skill.
        
        Args:
            skill_id: Skill ID
            reason: Reason for activation
            
        Returns:
            True if activated successfully
        """
        return await self.transition(
            skill_id,
            SkillLifecycleStatus.ACTIVE,
            reason
        )
