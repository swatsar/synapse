"""
Unified Runtime Container for Synapse v3.4.1.

Implements SYSTEM_SPEC v3.4.1 Phase 1 & 2:
- Single source of truth for runtime assembly & Dependency Injection
- Service lifecycle management (start, stop, graceful shutdown)
- Health aggregation across all platform subsystems
- Background worker task tracking and cleanup

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

from synapse.api.invocation_service import InvocationService, get_invocation_service
from synapse.api.workspace_store import WorkspaceStore, default_workspace_store
from synapse.harnesses.hallmark import HallmarkHarness, get_hallmark_harness
from synapse.integrations.browser_controller import SecureBrowserController, get_browser_controller
from synapse.integrations.codex_engine import CodexEngine, get_codex_engine
from synapse.llm.credentials.store import CredentialStore, default_credential_store
from synapse.llm.omnirouter import OmniRouter, get_omnirouter
from synapse.llm.providers.registry import ProviderRegistry
from synapse.memory.vault import MemoryVault, get_memory_vault
from synapse.runtime.worker_backend import IsolatedWorkerBackend
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.skills.dynamic.registry import SkillRegistry
from synapse.skills.library import SkillLibrary, get_skill_library
from synapse.work.engine import WorkEngine

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.runtime.container")


@dataclass
class SubsystemHealth:
    name: str
    status: str  # healthy, degraded, unhealthy, disabled
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "details": self.details,
            "error": self.error,
            "protocol_version": self.protocol_version,
        }


class RuntimeContainer:
    """Central Dependency Injection and Service Lifecycle Container."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        workspace_root: Optional[str | Path] = None,
        workspace_store: Optional[WorkspaceStore] = None,
        credential_store: Optional[CredentialStore] = None,
        provider_registry: Optional[ProviderRegistry] = None,
        omnirouter: Optional[OmniRouter] = None,
        capability_manager: Optional[CapabilityManager] = None,
        execution_guard: Optional[ExecutionGuard] = None,
        invocation_service: Optional[InvocationService] = None,
        skill_library: Optional[SkillLibrary] = None,
        dynamic_skill_registry: Optional[SkillRegistry] = None,
        memory_vault: Optional[MemoryVault] = None,
        benchmark_harness: Optional[HallmarkHarness] = None,
        codex_engine: Optional[CodexEngine] = None,
        browser_controller: Optional[SecureBrowserController] = None,
        worker_backend: Optional[IsolatedWorkerBackend] = None,
        work_engine: Optional[WorkEngine] = None,
    ):
        self.workspace_root = Path(workspace_root or os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve()

        # Core Security & Governance
        self.capability_manager = capability_manager or CapabilityManager()
        self.execution_guard = execution_guard or ExecutionGuard(capability_manager=self.capability_manager)
        self.invocation_service = invocation_service or InvocationService(
            capability_manager=self.capability_manager
        )

        # LLM, Credentials & Routing
        self.credential_store = credential_store or default_credential_store()
        if provider_registry is not None:
            self.provider_registry = provider_registry
        else:
            from synapse.api.routes.providers import provider_service
            self.provider_registry = provider_service.registry

        self.omnirouter = omnirouter or get_omnirouter()

        # Workspaces, Skills & Execution
        self.workspace_store = workspace_store or default_workspace_store()
        self.skill_library = skill_library or get_skill_library()
        self.dynamic_skill_registry = dynamic_skill_registry or SkillRegistry(capability_manager=self.capability_manager)
        self.memory_vault = memory_vault or get_memory_vault(
            self.workspace_root / ".synapse" / "memory_vault.json"
        )
        self.benchmark_harness = benchmark_harness or get_hallmark_harness()
        self.codex_engine = codex_engine or get_codex_engine(self.workspace_root)
        self.browser_controller = browser_controller or get_browser_controller()
        self.worker_backend = worker_backend or IsolatedWorkerBackend()
        work_db = self.workspace_root / ".synapse" / "work.sqlite3"
        self.work_engine = work_engine or WorkEngine(work_db)

        # Lifecycle State
        self._is_started = False
        self._background_tasks: Set[asyncio.Task] = set()
        self._orchestrator: Any = None
        self._checkpoint_manager: Any = None

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def orchestrator(self) -> Any:
        return self._orchestrator

    @orchestrator.setter
    def orchestrator(self, orch: Any) -> None:
        self._orchestrator = orch
        if orch is not None and hasattr(orch, "checkpoint_manager"):
            self._checkpoint_manager = orch.checkpoint_manager

    @property
    def checkpoint_manager(self) -> Any:
        return self._checkpoint_manager

    async def start(self) -> None:
        """Initialize all subsystems and prepare for traffic."""
        if self._is_started:
            return

        logger.info("Initializing Synapse RuntimeContainer (root: %s)", self.workspace_root)

        # 1. Ensure provider registry loaded
        try:
            if hasattr(self.provider_registry, "reload"):
                await self.provider_registry.reload()
        except Exception as e:
            logger.warning("Failed to warm-load provider registry: %s", e)

        # 2. Check router availability (discover Ollama if running)
        try:
            if hasattr(self.omnirouter, "check_availability_async"):
                await self.omnirouter.check_availability_async()
        except Exception as e:
            logger.warning("Failed to warm-probe omnirouter: %s", e)

        self._is_started = True
        logger.info("Synapse RuntimeContainer started successfully")

    async def stop(self) -> None:
        """Gracefully terminate background workers and release database handles."""
        if not self._is_started:
            return

        logger.info("Stopping Synapse RuntimeContainer...")

        # 1. Cancel and await background tasks
        if self._background_tasks:
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        # 2. Close orchestrator & memory stores if present
        if self._orchestrator:
            try:
                mem = getattr(self._orchestrator, "memory_store", None)
                if mem and hasattr(mem, "close"):
                    res = mem.close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as e:
                logger.error("Error closing orchestrator memory: %s", e)
            self._orchestrator = None
            self._checkpoint_manager = None

        # 3. Close workspace store
        if self.workspace_store and hasattr(self.workspace_store, "close"):
            try:
                self.workspace_store.close()
            except Exception as e:
                logger.error("Error closing workspace store: %s", e)

        if self.work_engine:
            try:
                await self.work_engine.close()
            except Exception as e:
                logger.error("Error closing work engine: %s", e)

        self._is_started = False
        logger.info("Synapse RuntimeContainer stopped")

    def register_background_task(self, coro) -> asyncio.Task:
        """Track an asynchronous task within the container lifecycle."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(lambda t: self._background_tasks.discard(t))
        return task

    async def health(self) -> dict[str, Any]:
        """Perform honest readiness probe across all subsystems."""
        subsystems: dict[str, dict[str, Any]] = {}
        all_healthy = True

        # 1. Database / Workspace Store
        try:
            sessions = self.workspace_store.list_sessions()
            subsystems["workspace_store"] = SubsystemHealth(
                name="workspace_store",
                status="healthy",
                details={"sessions_accessible": True, "count": len(sessions)},
            ).to_dict()
        except Exception as e:
            all_healthy = False
            subsystems["workspace_store"] = SubsystemHealth(
                name="workspace_store",
                status="unhealthy",
                error=str(e),
            ).to_dict()

        # 2. Credential Store
        try:
            cred_health = await self.credential_store.health() if hasattr(self.credential_store, "health") else {"status": "ok"}
            subsystems["credentials"] = SubsystemHealth(
                name="credentials",
                status="healthy",
                details=cred_health,
            ).to_dict()
        except Exception as e:
            all_healthy = False
            subsystems["credentials"] = SubsystemHealth(
                name="credentials",
                status="degraded",
                error=str(e),
            ).to_dict()

        # 3. Provider Registry & OmniRouter
        try:
            providers = await self.provider_registry.list() if hasattr(self.provider_registry, "list") else []
            router_stats = self.omnirouter.get_stats() if hasattr(self.omnirouter, "get_stats") else {}
            subsystems["router"] = SubsystemHealth(
                name="router",
                status="healthy",
                details={
                    "registered_providers_count": len(providers),
                    "default_model": getattr(self.omnirouter, "default_model", "unknown"),
                    "stats": router_stats,
                },
            ).to_dict()
        except Exception as e:
            all_healthy = False
            subsystems["router"] = SubsystemHealth(
                name="router",
                status="degraded",
                error=str(e),
            ).to_dict()

        # 4. Isolated Worker Backend
        try:
            from synapse.runtime.worker_backend import is_docker_available
            docker_ok = is_docker_available()
            subsystems["worker_backend"] = SubsystemHealth(
                name="worker_backend",
                status="healthy",
                details={
                    "subprocess_isolation": True,
                    "container_isolation": docker_ok,
                },
            ).to_dict()
        except Exception as e:
            subsystems["worker_backend"] = SubsystemHealth(
                name="worker_backend",
                status="degraded",
                error=str(e),
            ).to_dict()

        overall_status = "healthy" if all_healthy else "degraded"

        return {
            "status": overall_status,
            "version": "3.4.1",
            "protocol_version": self.protocol_version,
            "timestamp": datetime.now(UTC).isoformat(),
            "subsystems": subsystems,
            "active_background_tasks": len(self._background_tasks),
        }


_GLOBAL_CONTAINER: Optional[RuntimeContainer] = None


def get_runtime_container() -> RuntimeContainer:
    """Retrieve application runtime container singleton."""
    global _GLOBAL_CONTAINER
    if _GLOBAL_CONTAINER is None:
        _GLOBAL_CONTAINER = RuntimeContainer()
    return _GLOBAL_CONTAINER


def set_runtime_container(container: RuntimeContainer) -> None:
    """Explicitly set application runtime container."""
    global _GLOBAL_CONTAINER
    _GLOBAL_CONTAINER = container


def reset_runtime_container() -> None:
    """Reset global container instance for testing."""
    global _GLOBAL_CONTAINER
    _GLOBAL_CONTAINER = None
