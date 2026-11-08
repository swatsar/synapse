"""Execution-only adapters for external coding-agent CLIs.

The adapters deliberately do not orchestrate tasks or grant permissions. They
launch an installed CLI only when explicitly enabled, keep the workspace
scoped, parse JSONL events losslessly enough for an execution receipt, and
return unavailable/failed outcomes instead of synthetic success.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import signal
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"


@dataclass(frozen=True)
class HarnessRequest:
    task_id: str
    run_id: str
    prompt: str
    workspace_id: str | None = None
    capabilities: tuple[str, ...] = ()
    budget_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessResult:
    success: bool
    output: str = ""
    artifacts: tuple[str, ...] = ()
    error: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    events: tuple[dict[str, Any], ...] = ()
    receipt: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION


class HarnessAdapter(ABC):
    name = "abstract"

    @abstractmethod
    async def execute(self, request: HarnessRequest) -> HarnessResult:
        """Execute one bounded request and return a truthful receipt."""


class UnconfiguredHarness(HarnessAdapter):
    def __init__(self, name: str):
        self.name = name

    async def execute(self, request: HarnessRequest) -> HarnessResult:
        return HarnessResult(False, error=f"harness {self.name} is not configured")


def _enabled() -> bool:
    return os.getenv("SYNAPSE_EXECUTORS_ENABLED", "").lower() in {"1", "true", "yes"}


def _workspace(request: HarnessRequest) -> Path | None:
    raw = request.metadata.get("workspace_root") or request.workspace_id
    if not raw:
        return None
    path = Path(str(raw)).expanduser().resolve()
    if not path.is_dir():
        return None
    return path


def _write_authorized(request: HarnessRequest, workspace: Path, write_enabled: bool) -> bool:
    """Require per-run confirmation and a declared workspace scope for writes."""
    if not write_enabled:
        return True
    if request.metadata.get("write_confirmation") is not True:
        return False
    raw_scope = request.metadata.get("workspace_scope")
    if not raw_scope:
        return False
    scope = Path(str(raw_scope)).expanduser().resolve()
    try:
        workspace.relative_to(scope)
    except ValueError:
        return False
    return scope.is_dir()


def _safe_env() -> dict[str, str]:
    """Pass only non-secret process settings; CLIs resolve auth themselves."""
    allowed = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
        "HOME", "USERPROFILE", "LANG", "LC_ALL", "COMSPEC", "CODEX_HOME",
        "CLAUDE_CONFIG_DIR", "NO_COLOR",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def _text_from(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_text_from(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "result", "output"):
            if key in value:
                text = _text_from(value[key])
                if text:
                    return text
    return ""


def _normalize_command(value: Any) -> list[str]:
    """Normalize a persisted/explicit command override to a non-empty argv list."""
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, (list, tuple)) and value and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    return []


def parse_jsonl(stdout: str) -> tuple[tuple[dict[str, Any], ...], str]:
    """Parse complete JSONL lines and retain unknown events for the receipt."""
    events: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"type": "unparsed_line", "line": line[:4000]})
            continue
        if not isinstance(event, dict):
            events.append({"type": "unknown_event", "value": event})
            continue
        events.append(event)
        event_type = str(event.get("type", ""))
        if event_type in {"result", "agent_message", "assistant", "message", "final"}:
            text = _text_from(event.get("result", event.get("message", event)))
            if text:
                text_parts.append(text)
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"}:
            text = _text_from(item)
            if text:
                text_parts.append(text)
    return tuple(events), "\n".join(dict.fromkeys(text_parts))


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        # Terminate descendants too; the CLI may spawn a model/helper process.
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/PID", str(process.pid), "/T", "/F",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        if process.returncode is None:
            process.kill()
            await process.wait()


class ExternalCliHarness(HarnessAdapter):
    """Common bounded subprocess implementation for CLI-based harnesses."""

    command: str = ""

    def __init__(self, *, executable: str | None = None, enabled: bool | None = None,
                 timeout_seconds: float = 120.0, write_enabled: bool = False,
                 command: list[str] | tuple[str, ...] | str | None = None):
        self.executable = executable or self.command
        configured: dict[str, Any] = {}
        if enabled is None or timeout_seconds == 120.0 or not write_enabled:
            try:
                from synapse.integrations.control_plane import get_control_plane
                configured = get_control_plane().executor_config().get(self.name, {})
            except (OSError, TypeError, ValueError):
                configured = {}
        self.enabled = bool(configured["enabled"]) if enabled is None and "enabled" in configured else (_enabled() if enabled is None else enabled)
        self.timeout_seconds = float(configured.get("timeout_seconds", timeout_seconds))
        self.write_enabled = bool(configured.get("write_enabled", write_enabled))
        # An explicit argv (for example [node, codex.js] for npm-wrapped CLIs)
        # overrides plain executable resolution; persisted config wins last.
        self.command_argv: list[str] = _normalize_command(command) if command else []
        configured_command = _normalize_command(configured.get("command"))
        if configured_command:
            self.command_argv = configured_command

    @abstractmethod
    def build_argv(self, prefix: list[str], request: HarnessRequest, workspace: Path) -> list[str]:
        """Build an argv-only command for the concrete CLI from the resolved prefix."""

    async def execute(self, request: HarnessRequest) -> HarnessResult:
        if not self.enabled:
            return HarnessResult(False, error=f"harness {self.name} is not configured; set SYNAPSE_EXECUTORS_ENABLED=1 for opt-in")
        workspace = _workspace(request)
        if workspace is None:
            return HarnessResult(False, error="executor workspace_root is required and must be an existing directory")
        if not _write_authorized(request, workspace, self.write_enabled):
            return HarnessResult(False, error="write mode requires explicit write_confirmation and workspace_scope containing workspace_root")
        prefix = list(self.command_argv)
        if not prefix:
            executable = shutil.which(self.executable)
            if executable is None:
                return HarnessResult(False, error=f"executor executable not found: {self.executable}")
            prefix = [executable]
        if os.name == "nt" and prefix[0].lower().endswith((".cmd", ".bat")):
            prefix = ["cmd.exe", "/c", *prefix]
        if not request.prompt.strip():
            return HarnessResult(False, error="executor prompt is empty")
        argv = self.build_argv(prefix, request, workspace)
        started = asyncio.get_running_loop().time()
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workspace),
                env=_safe_env(),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(os.name != "nt"),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            if process is not None:
                await _terminate_process(process)
            return HarnessResult(
                False,
                error=f"executor timed out after {self.timeout_seconds:g}s",
                receipt={"status": "timed_out", "argv": argv[0:2], "workspace": str(workspace)},
            )
        except (OSError, asyncio.CancelledError) as exc:
            if process is not None:
                await _terminate_process(process)
            if isinstance(exc, asyncio.CancelledError):
                raise
            return HarnessResult(False, error=f"executor launch failed: {exc}")

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        events, output = parse_jsonl(stdout)
        duration_ms = round((asyncio.get_running_loop().time() - started) * 1000, 2)
        receipt = {
            "status": "completed" if process.returncode == 0 else "failed",
            "executor": self.name,
            "returncode": process.returncode,
            "duration_ms": duration_ms,
            "workspace": str(workspace),
            "write_enabled": self.write_enabled,
            "write_authorized": self.write_enabled and request.metadata.get("write_confirmation") is True,
            "event_count": len(events),
            "stderr_present": bool(stderr),
            "argv": argv[0:2],
        }
        if process.returncode != 0:
            return HarnessResult(False, output=output, error=(stderr.strip() or f"executor exited with code {process.returncode}"), events=events, receipt=receipt)
        if not output:
            return HarnessResult(False, error="executor returned no final message", events=events, receipt=receipt)
        return HarnessResult(True, output=output, events=events, receipt=receipt)


class CodexHarness(ExternalCliHarness):
    name = "codex"
    command = "codex"

    def build_argv(self, prefix: list[str], request: HarnessRequest, workspace: Path) -> list[str]:
        sandbox = "workspace-write" if self.write_enabled else "read-only"
        return [
            *prefix, "exec", "--json", "--ephemeral", "--ignore-user-config",
            "--sandbox", sandbox, "--cd", str(workspace), request.prompt,
        ]


class ClaudeCodeHarness(ExternalCliHarness):
    name = "claude_code"
    command = "claude"

    def build_argv(self, prefix: list[str], request: HarnessRequest, workspace: Path) -> list[str]:
        tools = "Read,Glob,Grep,Write,Edit" if self.write_enabled else "Read,Glob,Grep"
        permission_mode = "acceptEdits" if self.write_enabled else "dontAsk"
        return [
            *prefix, "-p", request.prompt, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--safe-mode", "--strict-mcp-config",
            "--permission-mode", permission_mode, "--tools", tools,
            "--add-dir", str(workspace),
        ]


class HermesHarness(UnconfiguredHarness):
    def __init__(self):
        super().__init__("hermes")


class AgentZeroHarness(UnconfiguredHarness):
    def __init__(self):
        super().__init__("agent_zero")


__all__ = [
    "HarnessRequest", "HarnessResult", "HarnessAdapter", "UnconfiguredHarness",
    "ExternalCliHarness", "CodexHarness", "ClaudeCodeHarness", "HermesHarness",
    "AgentZeroHarness", "parse_jsonl",
]
