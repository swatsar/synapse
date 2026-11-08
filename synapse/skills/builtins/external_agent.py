"""Delegate a bounded task to an external coding-agent CLI (Claude Code, Codex).

The skill runs the installed CLI through the harness layer with a scoped
workspace, returning the agent's real final message plus a truthful receipt.
Nothing is synthesized: unavailable/failed outcomes are surfaced as errors.
"""
from __future__ import annotations

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
        or os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())
    ).expanduser().resolve()

    write_enabled = bool(params.get("write_enabled", False))
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
        },
    )

    timeout_seconds = params.get("timeout_seconds")
    harness = harness_cls() if timeout_seconds is None else harness_cls(timeout_seconds=float(timeout_seconds))
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
