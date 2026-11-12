"""Delegate a bounded task to an external coding-agent CLI (Claude Code, Codex).

The skill runs the installed CLI through the harness layer with a scoped
workspace, returning the agent's real final message plus a truthful receipt.
Nothing is synthesized: unavailable/failed outcomes are surfaced as errors.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import os
from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext


async def execute_external_agent(ctx: ExecutionContext, agent: str = "codex", task: str = "", **params):
    """Run one bounded prompt through an external agent CLI and return its output."""
    from synapse.harnesses import CodexHarness, ClaudeCodeHarness, HarnessRequest

    if not task.strip():
        return {"success": False, "error": "external agent prompt is empty"}

    agents = {
        "codex": CodexHarness,
        "claude_code": ClaudeCodeHarness,
    }
    normalized = str(agent).strip().lower().replace("-", "_")
    harness_cls = agents.get(normalized)
    if harness_cls is None:
        available = ", ".join(sorted(agents))
        return {"success": False, "error": f"unknown external agent '{agent}'; available: {available}"}

    workspace_root = Path(
        params.get("workspace_root")
        or os.getenv("SYNAPSE_WORKSPACE_ROOT")
        or getattr(getattr(ctx, "memory_store", None), "workspace_root", None)
        or os.getcwd()
    ).expanduser().resolve()

    write_enabled = bool(params.get("write_enabled", False))
    model = params.get("model")
    request = HarnessRequest(
        task_id=str(params.get("task_id") or ctx.trace_id or "external_agent"),
        run_id=str(ctx.trace_id or "external_agent"),
        prompt=task,
        workspace_id=str(workspace_root),
        capabilities=("fs:read",) if not write_enabled else ("fs:read", "fs:write"),
        metadata={
            "workspace_root": str(workspace_root),
            "write_enabled": write_enabled,
            "write_confirmation": write_enabled and bool(ctx.approval_granted),
            "workspace_scope": str(workspace_root),
            **({"model": str(model)} if model else {}),
        },
    )

    timeout_seconds = params.get("timeout_seconds")
    # The settings UI enables an executor by persisting its config. Pass that
    # decision explicitly so a chat run does not depend on a process-wide env
    # variable that the UI cannot change.
    from synapse.integrations.control_plane import get_control_plane

    persisted = get_control_plane().executor_config().get(normalized, {})
    harness_kwargs: dict[str, Any] = {}
    if "enabled" in persisted:
        harness_kwargs["enabled"] = bool(persisted["enabled"])
    if persisted.get("command"):
        harness_kwargs["command"] = persisted["command"]
    if timeout_seconds is not None:
        harness_kwargs["timeout_seconds"] = float(timeout_seconds)
    harness = harness_cls(**harness_kwargs)
    # Never let a persisted write flag silently escalate a read-only chat run.
    harness.write_enabled = bool(write_enabled)
    result = await harness.execute(request)

    payload: dict[str, Any] = {
        "success": result.success,
        "agent": normalized,
        "content": result.output,
        "receipt": result.receipt,
        "write_enabled": write_enabled,
    }
    if result.error:
        payload["error"] = result.error
    if result.usage:
        payload["usage"] = result.usage
    return payload


__all__ = ["execute_external_agent"]
