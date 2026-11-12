"""Discovery of external coding-agent CLIs without a Velly dependency.

Velly has been replaced by OpenCode as Synapse's primary model/runtime surface.
External coding agents (Codex CLI, Claude Code) are ordinary executables on the
machine, so they are discovered from ``PATH`` and their standard install
locations only. No Velly configuration, workspace list or model catalog is read.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExternalAgent:
    """One external coding-agent CLI that Synapse may delegate a task to."""

    agent_id: str
    display_name: str
    version: str | None = None
    install_via: str = "path"
    available: bool = False
    argv: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.agent_id,
            "display_name": self.display_name,
            "version": self.version,
            "install_via": self.install_via,
            "available": self.available,
            "argv": list(self.argv),
            "protocol_version": PROTOCOL_VERSION,
        }


def _first_executable(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _claude_argv() -> list[str]:
    found = shutil.which("claude") or shutil.which("claude.exe")
    if found:
        return [found]
    executable = _first_executable([
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "local" / "claude.exe",
        Path.home() / ".claude" / "local" / "claude",
    ])
    return [str(executable)] if executable else []


def _codex_argv() -> list[str]:
    found = shutil.which("codex") or shutil.which("codex.exe")
    if found:
        return [found]
    executable = _first_executable([
        Path.home() / ".local" / "bin" / "codex.exe",
        Path.home() / ".local" / "bin" / "codex",
    ])
    return [str(executable)] if executable else []


def detect_agents() -> list[ExternalAgent]:
    """Return external agent CLIs with truthful availability and argv."""
    claude_argv = _claude_argv()
    codex_argv = _codex_argv()
    return [
        ExternalAgent(
            agent_id="claude_code",
            display_name="Claude Code",
            install_via="path",
            available=bool(claude_argv),
            argv=tuple(claude_argv),
        ),
        ExternalAgent(
            agent_id="codex",
            display_name="Codex",
            install_via="path",
            available=bool(codex_argv),
            argv=tuple(codex_argv),
        ),
    ]


def sync_agents_to_control_plane() -> list[dict[str, Any]]:
    """Persist discovered external agent commands into the control plane.

    Only non-secret fields are written: the command argv and enabled flag. This
    makes externally installed CLIs directly usable by the harness layer without
    reading another application's configuration.
    """
    from synapse.integrations.control_plane import get_control_plane

    control_plane = get_control_plane()
    synced: list[dict[str, Any]] = []
    for agent in detect_agents():
        if not agent.available:
            continue
        current = control_plane.executor_config().get(agent.agent_id, {})
        config = control_plane.update_executor(
            agent.agent_id,
            enabled=bool(current.get("enabled", False)),
            write_enabled=bool(current.get("write_enabled", False)),
            command=list(agent.argv),
        )
        if agent.version:
            from synapse.integrations import control_plane as _cp

            _cp._write("executors.json", {
                **_cp._read("executors.json", {}),
                agent.agent_id: {**current, **config, "version": agent.version},
            })
        synced.append({
            "id": agent.agent_id,
            "argv": list(agent.argv),
            "version": agent.version,
        })
    return synced


__all__ = [
    "ExternalAgent",
    "detect_agents",
    "sync_agents_to_control_plane",
]
