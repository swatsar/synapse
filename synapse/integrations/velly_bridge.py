"""Read-only discovery bridge for the locally installed Velly desktop app.

Velly wraps Claude Code and Codex CLIs and records its agent toolchain and
chat configuration under %APPDATA%/Velly. This module only READS that state
so Synapse can (a) detect installed agents even when they are not on PATH and
(b) offer Velly-configured agents/models as connection candidates. It never
writes into Velly's directory and never reads secret files (auth.json).
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APPDATA = os.getenv("APPDATA", "")
VELLY_DIR = Path(APPDATA) / "Velly" if APPDATA else None

# npm-wrapped CLIs resolve through node.exe plus the package's JS entrypoint.
_NPM_TOOLS = Path(APPDATA) / "Velly" / "agent-tools" if APPDATA else None

_SECRET_FILES = {"auth.bin", "auth.json", "auth.json.lock", "auth.lock", ".updaterId"}


@dataclass(frozen=True)
class VellyAgent:
    """One agent CLI installed and managed by Velly."""

    agent_id: str
    display_name: str
    version: str | None
    install_via: str
    available: bool
    argv: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.agent_id,
            "display_name": self.display_name,
            "version": self.version,
            "install_via": self.install_via,
            "available": self.available,
            "argv": self.argv,
        }


def _safe_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.name.lower() in _SECRET_FILES or not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _node_exe() -> Path | None:
    if _NPM_TOOLS is None:
        return None
    candidate = _NPM_TOOLS / "node" / "node.exe"
    return candidate if candidate.is_file() else None


def _codex_js() -> Path | None:
    if _NPM_TOOLS is None:
        return None
    candidate = _NPM_TOOLS / "npm" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    return candidate if candidate.is_file() else None


def detect_agents() -> list[VellyAgent]:
    """Return Velly-managed agent CLIs with truthful availability and argv."""
    updates = _safe_json(VELLY_DIR / "agent-updates.json") if VELLY_DIR else None
    agents: list[VellyAgent] = []

    # Claude Code: Velly installs a native exe under ~/.local/bin.
    claude_info = (updates or {}).get("claude", {})
    claude_exe = Path.home() / ".local" / "bin" / "claude"
    claude_on_path = shutil.which("claude")
    resolved_claude = claude_exe if claude_exe.is_file() else (Path(claude_on_path) if claude_on_path else None)
    agents.append(VellyAgent(
        agent_id="claude_code",
        display_name="Claude Code",
        version=claude_info.get("version"),
        install_via=str(claude_info.get("via", "unknown")),
        available=resolved_claude is not None,
        argv=[str(resolved_claude)] if resolved_claude else [],
    ))

    # Codex: Velly installs through its bundled npm; run via node + codex.js.
    codex_info = (updates or {}).get("codex", {})
    node = _node_exe()
    codex_js = _codex_js()
    codex_argv = [str(node), str(codex_js)] if node and codex_js else []
    if not codex_argv:
        codex_on_path = shutil.which("codex")
        codex_argv = [codex_on_path] if codex_on_path else []
    agents.append(VellyAgent(
        agent_id="codex",
        display_name="Codex",
        version=codex_info.get("version"),
        install_via=str(codex_info.get("via", "unknown")),
        available=bool(codex_argv),
        argv=codex_argv,
    ))
    return agents


def velly_status() -> dict[str, Any]:
    """Summarize Velly app state without touching secret files."""
    installed = bool(VELLY_DIR and VELLY_DIR.is_dir())
    result: dict[str, Any] = {
        "status": "installed" if installed else "not_found",
        "app_dir": str(VELLY_DIR) if installed else None,
        "agents": [agent.to_dict() for agent in detect_agents()],
        "workspaces": [],
        "chat_config": {},
        "protocol_version": "1.0",
    }
    if not installed:
        return result
    config = _safe_json(VELLY_DIR / "config.json") or {}
    workspaces = [str(item) for item in config.get("workspaces", []) if isinstance(item, str)]
    result["workspaces"] = workspaces
    result["chat_config"] = {
        "last_model": config.get("lastModel"),
        "agent_perm": config.get("agentPerm"),
        "effort": config.get("effort"),
        "browser_agent": bool(config.get("prefs", {}).get("browserAgent", False)),
    }
    return result


def sync_agents_to_control_plane() -> list[dict[str, Any]]:
    """Persist discovered Velly agent commands into the executor control plane.

    Only non-secret fields are written: the command argv, enabled flag. This
    makes externally installed CLIs directly usable by the harness layer.
    """
    from synapse.integrations.control_plane import get_control_plane

    control_plane = get_control_plane()
    synced: list[dict[str, Any]] = []
    for agent in detect_agents():
        if not agent.available:
            continue
        payload: dict[str, Any] = {"command": agent.argv}
        if agent.version:
            payload["version"] = agent.version
        current = control_plane.executor_config().get(agent.agent_id, {})
        payload["enabled"] = bool(current.get("enabled", False))
        payload["write_enabled"] = bool(current.get("write_enabled", False))
        config = control_plane.update_executor(agent.agent_id, enabled=payload["enabled"], write_enabled=payload["write_enabled"])
        # command/version go through the same store, guarded as non-secret.
        merged = {**current, **payload, **config}
        from synapse.integrations import control_plane as _cp
        _cp._write("executors.json", {
            **_cp._read("executors.json", {}),
            agent.agent_id: merged,
        })
        synced.append({"id": agent.agent_id, "argv": agent.argv, "version": agent.version})
    return synced


__all__ = ["VellyAgent", "detect_agents", "velly_status", "sync_agents_to_control_plane"]
