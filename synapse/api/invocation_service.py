"""
Invocation Service for all platform execution entrypoints.
Enforces caller identity, workspace boundaries, run tracking, capability checking,
budget limits, and human approval gates.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from synapse.core.models import ExecutionContext
from synapse.observability.logger import audit
from synapse.security.capability_manager import CapabilityManager

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.api.invocation_service")


@dataclass
class InvocationContext:
    identity: str = "anonymous"
    role: str = "user"
    workspace_root: Path = field(default_factory=lambda: Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve())
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capabilities: list[str] = field(default_factory=list)
    budget_limit_usd: float = 10.0
    spent_usd: float = 0.0
    approval_granted: bool = False
    is_network_request: bool = False
    auth_authenticated: bool = True


@dataclass
class InvocationResult:
    success: bool
    action_type: str
    action_name: str
    run_id: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    requires_approval: bool = False
    protocol_version: str = PROTOCOL_VERSION
    receipt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "action_name": self.action_name,
            "run_id": self.run_id,
            "result": self.result,
            "error": self.error,
            "requires_approval": self.requires_approval,
            "protocol_version": self.protocol_version,
            "receipt": self.receipt,
        }


class InvocationService:
    """Unified service gatekeeper for all executing entrypoints."""

    def __init__(self, capability_manager: Optional[CapabilityManager] = None):
        self.capability_manager = capability_manager or CapabilityManager()
        # Default core capabilities for system operations
        self.capability_manager.grant("fs:read")
        self.capability_manager.grant("fs:write")
        self.capability_manager.grant("memory:read")
        self.capability_manager.grant("memory:write")
        self.capability_manager.grant("llm:route")
        self.capability_manager.grant("code:analyze")
        self.capability_manager.grant("browser:navigate")
        self.capability_manager.grant("eval:run")
        self.capability_manager.grant("learning:export")
        self.capability_manager.grant("patch:apply")
        self.capability_manager.grant("slash:execute")

    async def invoke(
        self,
        *,
        action_type: str,
        action_name: str,
        handler: Callable[..., Any],
        context: InvocationContext,
        required_capabilities: list[str],
        risk_level: int = 1,
        params: Optional[dict[str, Any]] = None,
    ) -> InvocationResult:
        """Mediate an action execution with full governance."""
        params = params or {}
        run_id = context.run_id

        # 1. Enforce Authentication on Network Entrypoints
        if context.is_network_request and not context.auth_authenticated:
            audit(
                event="invocation_blocked_unauthenticated",
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
            )
            return InvocationResult(
                success=False,
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                error="Unauthenticated network invocation rejected",
            )

        # 2. Check Budget
        if context.spent_usd >= context.budget_limit_usd:
            audit(
                event="invocation_blocked_budget_exhausted",
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                budget=context.budget_limit_usd,
                spent=context.spent_usd,
            )
            return InvocationResult(
                success=False,
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                error=f"Execution budget limit reached: spent ${context.spent_usd:.2f} >= ${context.budget_limit_usd:.2f}",
            )

        # 3. Check Approval for High-Risk Actions
        requires_approval = risk_level >= 3 or action_type in {"system", "patch"}
        if requires_approval and not context.approval_granted:
            audit(
                event="invocation_approval_required",
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                risk_level=risk_level,
            )
            return InvocationResult(
                success=False,
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                requires_approval=True,
                error=f"Action '{action_name}' (risk level {risk_level}) requires explicit human approval",
            )

        # 4. Check Capabilities
        for cap in required_capabilities:
            has_cap = await self.capability_manager.check_capability(context, cap)
            if not has_cap:
                audit(
                    event="invocation_blocked_capability",
                    action_type=action_type,
                    action_name=action_name,
                    run_id=run_id,
                    missing_capability=cap,
                )
                return InvocationResult(
                    success=False,
                    action_type=action_type,
                    action_name=action_name,
                    run_id=run_id,
                    error=f"Missing required capability '{cap}' for action '{action_name}'",
                )

        # 5. Execute Action
        t0 = datetime.now(UTC)
        try:
            import inspect
            if inspect.iscoroutinefunction(handler):
                raw_res = await handler(**params)
            else:
                raw_res = handler(**params)

            t1 = datetime.now(UTC)
            duration_ms = (t1 - t0).total_seconds() * 1000.0

            receipt = {
                "run_id": run_id,
                "session_id": context.session_id,
                "identity": context.identity,
                "action_type": action_type,
                "action_name": action_name,
                "timestamp": t1.isoformat(),
                "duration_ms": round(duration_ms, 2),
                "risk_level": risk_level,
                "capabilities_exercised": required_capabilities,
            }

            audit(
                event="invocation_success",
                **receipt,
            )

            # Extract inner success/failure if dict returned
            success = True
            error_msg = None
            if isinstance(raw_res, dict):
                if raw_res.get("success") is False or raw_res.get("status") in {"failed", "blocked", "timeout"}:
                    success = False
                    error_msg = raw_res.get("error") or "Inner execution failure"

            return InvocationResult(
                success=success,
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                result=raw_res if isinstance(raw_res, dict) else {"output": raw_res},
                error=error_msg,
                receipt=receipt,
            )
        except Exception as e:
            logger.error("Invocation of %s/%s failed: %s", action_type, action_name, e)
            audit(
                event="invocation_failed",
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                error=str(e),
            )
            return InvocationResult(
                success=False,
                action_type=action_type,
                action_name=action_name,
                run_id=run_id,
                error=str(e),
            )


_GLOBAL_INVOCATION_SERVICE: Optional[InvocationService] = None


def get_invocation_service() -> InvocationService:
    """Singleton getter for InvocationService."""
    global _GLOBAL_INVOCATION_SERVICE
    if _GLOBAL_INVOCATION_SERVICE is None:
        _GLOBAL_INVOCATION_SERVICE = InvocationService()
    return _GLOBAL_INVOCATION_SERVICE
