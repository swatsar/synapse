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

import ast
import importlib.util
import inspect
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from synapse.core.isolation_policy import RuntimeIsolationType
from synapse.core.models import ExecutionContext, ResourceLimits, SkillManifest
from synapse.observability.logger import audit
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard


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


class SkillRecord:
    """Record for a skill with lifecycle tracking."""

    def __init__(
        self,
        skill_id: str,
        manifest: SkillManifest,
        handler: Optional[Callable] = None,
        status: SkillLifecycleStatus = SkillLifecycleStatus.GENERATED,
        file_path: Optional[str] = None,
        is_builtin: bool = False,
    ):
        self.skill_id = skill_id
        self.manifest = manifest
        self.handler = handler
        self.status = status
        self.file_path = file_path
        self.is_builtin = is_builtin
        self.created_at = datetime.now(UTC).isoformat()
        self.updated_at = datetime.now(UTC).isoformat()
        self.status_history: list[dict] = [{
            "status": status.value,
            "timestamp": self.created_at,
            "reason": "initial"
        }]
        self.protocol_version = PROTOCOL_VERSION

    def to_dict(self) -> dict:
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
    VALID_TRANSITIONS: dict[SkillLifecycleStatus, list[SkillLifecycleStatus]] = {
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
        self._registry: dict[str, SkillRecord] = {}
        self._manifests: dict[str, SkillManifest] = {}
        self.capability_manager = capability_manager
        # Create default limits for the guard
        default_limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        self.guard = ExecutionGuard(capability_manager=capability_manager, limits=default_limits)

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
        record.updated_at = datetime.now(UTC).isoformat()
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
        """Get a skill handler by name."""
        record = self._registry.get(name)
        if record is None:
            record = next((r for r in self._registry.values() if r.manifest.name == name), None)
        if record is None:
            raise KeyError(f"Skill {name} not found")
        if record.handler is not None:
            return record.handler
        async def _isolated_proxy(context, **params):
            return await self.execute(record.manifest.name, context, **params)
        return _isolated_proxy

    def register_builtin(self, manifest: SkillManifest, handler: Callable) -> str:
        """Register a trusted built-in skill directly in the active state.

        Dynamically generated skills must still use ``register`` and the full
        lifecycle. Built-ins are shipped and reviewed with the application.
        """
        manifest.trust_level = "trusted"
        self._validate_manifest(manifest)
        skill_id = str(uuid.uuid4())
        self._registry[skill_id] = SkillRecord(
            skill_id=skill_id,
            manifest=manifest,
            handler=handler,
            status=SkillLifecycleStatus.ACTIVE,
            is_builtin=True,
        )
        self._manifests[manifest.name] = manifest
        return skill_id

    async def list_active(self) -> list[dict]:
        """Return metadata for skills that are allowed to execute."""
        return [record.to_dict() for record in self.get_active_skills()]

    async def execute(
        self,
        name: str,
        context: ExecutionContext,
        **params,
    ) -> dict:
        """Execute an active skill with its manifest and security context."""
        record = next(
            (
                item for item in self.get_active_skills()
                if item.manifest.name == name
            ),
            None,
        )
        if record is None:
            raise LookupError(f"Active skill not found: {name}")

        check = await self.guard.check_execution_allowed(record, context)
        if not check.allowed:
            raise PermissionError(check.reason or f"Execution denied: {name}")

        required_iso = check.required_isolation
        if required_iso in (
            RuntimeIsolationType.SUBPROCESS,
            RuntimeIsolationType.SANDBOX,
            RuntimeIsolationType.CONTAINER,
        ):
            from synapse.runtime.worker_backend import IsolatedWorkerBackend
            if record.file_path:
                result = await IsolatedWorkerBackend.run_skill(
                    target_type="file",
                    file_path=record.file_path,
                    context=context,
                    params=params,
                    limits=self.guard.limits,
                    isolation_type=required_iso,
                )
            else:
                result = await IsolatedWorkerBackend.run_skill(
                    target_type="callable",
                    handler_callable=record.handler,
                    context=context,
                    params=params,
                    limits=self.guard.limits,
                    isolation_type=required_iso,
                )
            if not isinstance(result, dict):
                raise TypeError(f"Skill {name} must return a dictionary")
            return result

        # Main-process execution only for trusted built-in skills with low risk
        if not record.is_builtin:
            from synapse.runtime.worker_backend import IsolatedWorkerBackend
            result = await IsolatedWorkerBackend.run_skill(
                target_type="file" if record.file_path else "callable",
                file_path=record.file_path,
                handler_callable=record.handler,
                context=context,
                params=params,
                limits=self.guard.limits,
                isolation_type=RuntimeIsolationType.SUBPROCESS,
            )
            if not isinstance(result, dict):
                raise TypeError(f"Skill {name} must return a dictionary")
            return result

        handler = record.handler
        execute = handler.execute if hasattr(handler, "execute") else handler
        result = execute(context, **params)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, dict):
            raise TypeError(f"Skill {name} must return a dictionary")
        return result

    def get_by_id(self, skill_id: str) -> SkillRecord | None:
        """Get a skill record by ID.
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Skill record or None
        """
        return self._registry.get(skill_id)

    def get_status(self, skill_id: str) -> SkillLifecycleStatus | None:
        """Get the lifecycle status of a skill.
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Lifecycle status or None
        """
        record = self._registry.get(skill_id)
        return record.status if record else None

    def get_active_skills(self) -> list[SkillRecord]:
        """Get all active skills.
        
        Returns:
            List of active skill records
        """
        return [
            r for r in self._registry.values()
            if r.status == SkillLifecycleStatus.ACTIVE
        ]

    def get_skills_by_status(self, status: SkillLifecycleStatus) -> list[SkillRecord]:
        """Get all skills with a specific status.
        
        Args:
            status: Lifecycle status
            
        Returns:
            List of skill records
        """
        return [r for r in self._registry.values() if r.status == status]

    def _parse_manifest_from_ast(self, path: str) -> SkillManifest:
        """Parse skill file AST to extract manifest and ensure handler exists without executing code."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Skill file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=path)
        except Exception as exc:
            raise ValueError(f"Syntax error in skill file: {exc}")

        manifest_node = None
        func_names = set()

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "manifest":
                            manifest_node = node.value
                        else:
                            func_names.add(target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_names.add(node.name)

        if manifest_node is None:
            raise AttributeError(f"No manifest defined in {path}")

        manifest_kwargs: dict[str, Any] = {}
        if isinstance(manifest_node, ast.Call):
            for kw in manifest_node.keywords:
                try:
                    manifest_kwargs[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    pass
        elif isinstance(manifest_node, ast.Dict):
            try:
                manifest_kwargs = ast.literal_eval(manifest_node)
            except Exception as e:
                raise ValueError(f"Cannot parse manifest dict in {path}: {e}")
        else:
            raise ValueError("manifest must be a SkillManifest(...) call or dict")

        expected_handler = manifest_kwargs.get("handler", "handler")
        if "handler" not in func_names and expected_handler not in func_names:
            raise AttributeError(f"No handler defined in {path}")

        if not manifest_kwargs.get("name") or not manifest_kwargs.get("version"):
            raise ValueError("Invalid SkillManifest – missing name or version")

        return SkillManifest(**manifest_kwargs)

    async def load_from_path(self, path: str) -> str:
        """Load a Python file that defines a `manifest` and a `handler`.

        The manifest is parsed as DATA without executing untrusted code in the control plane.
        Capabilities are verified BEFORE registration and side effects.
        Execution is deferred to an isolated worker backend.

        Args:
            path: Path to skill file

        Returns:
            Skill ID
        """
        manifest = self._parse_manifest_from_ast(path)
        self._validate_manifest(manifest)

        # Capability check before any side effects or import!
        await self.capability_manager.check_capability(manifest.required_capabilities)

        skill_id = str(uuid.uuid4())
        record = SkillRecord(
            skill_id=skill_id,
            manifest=manifest,
            handler=None,  # Not imported into control plane
            status=SkillLifecycleStatus.GENERATED,
            file_path=path,
            is_builtin=False,
        )

        self._registry[skill_id] = record
        self._manifests[manifest.name] = manifest

        audit(
            event="skill_loaded_from_path",
            skill_id=skill_id,
            name=manifest.name,
            version=manifest.version,
            status=SkillLifecycleStatus.GENERATED.value,
            protocol_version=self.protocol_version,
        )

        return skill_id

    def list_skills(self) -> dict[str, SkillManifest]:
        """List all registered skills.
        
        Returns:
            Dictionary of skill names to manifests
        """
        return self._manifests.copy()

    def list_skills_with_status(self) -> list[dict]:
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
