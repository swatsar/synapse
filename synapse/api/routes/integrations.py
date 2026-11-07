"""Operator-facing integration inventory and explicit control-plane updates."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from synapse.harnesses import ClaudeCodeHarness, CodexHarness, HarnessRequest
from synapse.integrations.control_plane import get_control_plane
from synapse.integrations.velly_bridge import sync_agents_to_control_plane, velly_status
from synapse.plugins import PluginLifecycle

router = APIRouter()


class ExecutorUpdate(BaseModel):
    enabled: bool | None = None
    write_enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    command: list[str] | None = None


class McpUpdate(BaseModel):
    id: str
    transport: str
    endpoint: str | None = None
    command: str | None = None
    url: str | None = None
    args: list[str] = []
    display_name: str | None = None
    workspace_id: str | None = None
    tenant_id: str | None = None
    tool_groups: list[str] = []
    permissions: list[str] = []
    enabled: bool = True
    metadata: dict[str, Any] = {}


@router.get("")
async def integration_inventory() -> dict[str, Any]:
    """Expose truthful capabilities and persistent non-secret integration state."""
    control_plane = get_control_plane()
    mcp = control_plane.list_mcp(include_disabled=True)
    plugins = control_plane.list_plugins()
    executor_config = control_plane.executor_config()

    def executor_payload(executor_id: str, harness: Any, safe_mode: str, supports: list[str]) -> dict[str, Any]:
        config = executor_config.get(executor_id, {})
        write_enabled = bool(config.get("write_enabled", False))
        return {
            "id": executor_id,
            "status": "opt_in_cli_adapter",
            "configured": harness.enabled,
            "safe_mode": "workspace-write + explicit confirmation" if write_enabled else safe_mode,
            "write_enabled": write_enabled,
            "timeout_seconds": float(config.get("timeout_seconds", harness.timeout_seconds)),
            "supports": supports,
        }

    return {
        "mcp": {
            "status": "registry_available",
            "configured_servers": len(mcp),
            "servers": [item.to_dict() for item in mcp],
            "transports": ["stdio", "streamable_http"],
            "note": "Persisted declarations contain no credentials; live SDK connections remain execution-scoped.",
        },
        "plugins": {
            "status": "runtime_available",
            "configured_plugins": len(plugins),
            "plugins": [{"id": item.id, "state": item.state.value, "error": item.error, "manifest": item.manifest.to_dict()} for item in plugins],
            "note": "Manifest registration is separate from activation; lifecycle remains capability-gated.",
        },
        "executors": [
            executor_payload("codex", CodexHarness(), "read-only", ["jsonl", "timeout", "process_cleanup"]),
            executor_payload("claude_code", ClaudeCodeHarness(), "dontAsk + Read/Glob/Grep", ["stream-json", "timeout", "process_cleanup"]),
        ],
        "vally": {
            "status": "not_configured",
            "note": "No Velly agent protocol is configured in this runtime; browser QA is separate from an executor integration.",
        },
        "protocol_version": "1.0",
    }


@router.get("/mcp")
async def list_mcp() -> dict[str, Any]:
    return {"servers": [item.to_dict() for item in get_control_plane().list_mcp()], "protocol_version": "1.0"}


@router.put("/mcp/{server_id}")
async def upsert_mcp(server_id: str, data: McpUpdate) -> dict[str, Any]:
    if data.id != server_id:
        raise HTTPException(status_code=400, detail="server id does not match path")
    try:
        record = get_control_plane().upsert_mcp(data.model_dump(exclude_none=True))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"server": record.to_dict(), "protocol_version": "1.0"}


@router.delete("/mcp/{server_id}")
async def delete_mcp(server_id: str) -> dict[str, Any]:
    return {"deleted": get_control_plane().delete_mcp(server_id), "protocol_version": "1.0"}


@router.patch("/executors/{executor_id}")
async def update_executor(executor_id: str, data: ExecutorUpdate) -> dict[str, Any]:
    if executor_id not in {"codex", "claude_code"}:
        raise HTTPException(status_code=404, detail="executor not found")
    config = get_control_plane().update_executor(executor_id, **data.model_dump(exclude_none=True))
    return {"executor": executor_id, "config": config, "protocol_version": "1.0"}


@router.patch("/plugins/{plugin_id}")
async def update_plugin_state(plugin_id: str, state: PluginLifecycle) -> dict[str, Any]:
    record = get_control_plane().set_plugin_state(plugin_id, state)
    if record is None:
        raise HTTPException(status_code=404, detail="plugin not found")
    return {"plugin": {"id": record.id, "state": record.state.value, "error": record.error}, "protocol_version": "1.0"}


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    """List external coding-agent CLIs with real availability and persisted config."""
    control_plane = get_control_plane()
    config = control_plane.executor_config()
    agents = []
    for executor_id, harness, supports in (
        ("codex", CodexHarness(), "read-only", ["jsonl", "timeout", "process_cleanup"]),
        ("claude_code", ClaudeCodeHarness(), "read-only", ["stream-json", "timeout", "process_cleanup"]),
    ):
        persisted = config.get(executor_id, {})
        agents.append({
            "id": executor_id,
            "configured": harness.enabled,
            "enabled": bool(persisted.get("enabled", harness.enabled)),
            "write_enabled": bool(persisted.get("write_enabled", False)),
            "command": persisted.get("command"),
            "resolved_executable": harness.executable,
            "timeout_seconds": float(persisted.get("timeout_seconds", harness.timeout_seconds)),
            "supports": supports,
        })
    return {"agents": agents, "protocol_version": "1.0"}


@router.post("/agents/{agent_id}/connect")
async def connect_agent(agent_id: str) -> dict[str, Any]:
    """Persist the discovered CLI command into the control plane (opt-in enable)."""
    if agent_id not in {"codex", "claude_code"}:
        raise HTTPException(status_code=404, detail="agent not found")
    synced = sync_agents_to_control_plane()
    entry = next((item for item in synced if item["id"] == agent_id), None)
    if entry is None:
        raise HTTPException(status_code=409, detail="agent CLI was not found on this machine")
    return {"agent": entry, "connected": True, "protocol_version": "1.0"}


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20000)
    workspace_root: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    write_enabled: bool = False


@router.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, data: AgentRunRequest) -> dict[str, Any]:
    """Run one bounded task through an external agent CLI and return its receipt."""
    if agent_id not in {"codex", "claude_code"}:
        raise HTTPException(status_code=404, detail="agent not found")
    harness = CodexHarness() if agent_id == "codex" else ClaudeCodeHarness()
    if not harness.enabled:
        raise HTTPException(status_code=409, detail="agent is disabled; enable it in integrations first")
    workspace_root = Path(
        data.workspace_root or os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())
    ).expanduser().resolve()
    if not workspace_root.is_dir():
        raise HTTPException(status_code=422, detail="workspace_root must be an existing directory")
    request = HarnessRequest(
        task_id=f"api:{agent_id}",
        run_id=f"api:{agent_id}",
        prompt=data.task,
        workspace_id=str(workspace_root),
        metadata={
            "workspace_root": str(workspace_root),
            "write_enabled": data.write_enabled,
            "write_confirmation": data.write_enabled,
            "workspace_scope": str(workspace_root),
        },
    )
    if data.timeout_seconds is not None:
        harness.timeout_seconds = float(data.timeout_seconds)
    result = await harness.execute(request)
    return {
        "agent": agent_id,
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "receipt": result.receipt,
        "protocol_version": "1.0",
    }


@router.get("/velly")
async def get_velly_status() -> dict[str, Any]:
    """Read-only status of the locally installed Velly app and its agents."""
    return velly_status()


@router.post("/velly/sync")
async def sync_velly_agents() -> dict[str, Any]:
    """Persist discovered Velly agent commands into the executor control plane."""
    synced = sync_agents_to_control_plane()
    if not synced:
        raise HTTPException(status_code=409, detail="no available Velly-managed agent CLIs were found")
    return {"synced": synced, "protocol_version": "1.0"}


__all__ = ["router"]
