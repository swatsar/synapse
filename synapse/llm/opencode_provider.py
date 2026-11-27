"""Provider for models served by the local OpenCode runtime.

OpenCode's one-shot CLI returns assistant text using its built-in Build agent
with tool use denied. Discovery and quota state live in
``synapse.integrations.opencode_bridge``.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import asyncio
import ctypes
import json
import os
import shutil
import signal
import subprocess
import tempfile
from typing import Any

from synapse.config.settings import local_only_enabled, selected_opencode_enabled
from synapse.integrations.opencode_bridge import (
    find_opencode_cli,
    is_opencode_quota_exhausted,
    list_opencode_models,
    opencode_child_environment,
    quota_status,
    record_opencode_failure,
    record_opencode_success,
)

DEFAULT_TIMEOUT = 180.0
# OpenCode free models can reject custom agents and overrides of Build with
# a quota error even when the same model works with the stock agent.
_OPENCODE_AGENT = "build"


class OpenCodeQuotaExceeded(RuntimeError):
    """Raised when free OpenCode usage is exhausted and retrying is pointless."""

    def __init__(self, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = int(retry_after_seconds)


def _merge_config_content() -> dict[str, Any]:
    """Preserve inline settings while enforcing text-only OpenCode requests."""
    content: dict[str, Any] = {}
    raw = os.getenv("OPENCODE_CONFIG_CONTENT", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                content = parsed
        except ValueError:
            content = {}

    content.setdefault("$schema", "https://opencode.ai/config.json")
    content.setdefault("update", "disable")
    content.setdefault("share", "disabled")
    providers = content.setdefault("providers", {})
    if isinstance(providers, dict):
        providers.setdefault("opencode", {})
    # Allow only the OpenCode provider. This avoids accidentally routing a free
    # model through another configured provider.
    content["experimental"] = {
        "policies": [
            {"action": "provider.use", "resource": "*", "effect": "deny"},
            {"action": "provider.use", "resource": "opencode", "effect": "allow"},
            {"action": "tool.use", "resource": "*", "effect": "deny"},
        ]
    }
    agents = content.get("agents")
    if isinstance(agents, dict):
        agents.pop(_OPENCODE_AGENT, None)
    return content


# Lines the CLI appends when the free tier is exhausted. They are runtime
# notices, not assistant answers, so they must never be rendered as chat text.
_QUOTA_NOTICE_MARKERS = (
    "subscribe to opencode go",
    "free usage limit reached",
    "usage limit reached",
    "upgrade to continue",
)
_QUOTA_NOTICE_MAX_CHARS = 400


def _strip_quota_notice_lines(content: str) -> str:
    """Drop quota boilerplate lines while keeping a real answer around them."""
    kept = [
        line for line in content.splitlines()
        if not any(marker in line.casefold() for marker in _QUOTA_NOTICE_MARKERS)
    ]
    stripped = "\n".join(kept).strip()
    return stripped if stripped else content.strip()


def _is_quota_notice(content: str) -> bool:
    """True when the whole response is only an exhausted-quota notice."""
    from synapse.integrations.opencode_bridge import classify_opencode_error

    compact = " ".join(content.split())
    if not compact or len(compact) > _QUOTA_NOTICE_MAX_CHARS:
        return False
    if any(marker in compact.casefold() for marker in _QUOTA_NOTICE_MARKERS):
        return True
    return classify_opencode_error(compact) == "quota"


def _parse_events(stdout: str) -> tuple[list[str], str | None]:
    texts: list[str] = []
    error: str | None = None
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "error":
            raw = event.get("error") or event.get("message") or "OpenCode request failed"
            if isinstance(raw, dict):
                raw = raw.get("message") or raw.get("type") or json.dumps(raw, ensure_ascii=False)
            error = str(raw)
            continue
        if event.get("type") == "text":
            part = event.get("part") or {}
            text = part.get("text") if isinstance(part, dict) else None
            if not text:
                text = event.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return texts, error


def _attach_windows_job(process: subprocess.Popen):
    """Return a cleanup operation for the process and any inherited children."""
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    handle = kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
    try:
        if not handle or not kernel.AssignProcessToJobObject(job, handle):
            raise ctypes.WinError(ctypes.get_last_error())
    except OSError:
        kernel.CloseHandle(job)
        raise
    finally:
        if handle:
            kernel.CloseHandle(handle)

    def terminate() -> None:
        try:
            if not kernel.TerminateJobObject(job, 1):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(job)

    return terminate


def _terminate_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


async def _run_cancellable(args: list[str], timeout: float, **options: Any) -> subprocess.CompletedProcess:
    """Wait for the owned standalone process tree to stop before returning."""
    with subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=(os.name != "nt"), **options,
    ) as process:
        try:
            cleanup = _attach_windows_job(process) if os.name == "nt" else lambda: _terminate_group(process.pid)
        except OSError:
            process.kill()
            await asyncio.to_thread(process.communicate)
            raise
        waiter = asyncio.create_task(asyncio.to_thread(process.communicate, timeout=timeout))
        try:
            stdout, stderr = await asyncio.shield(waiter)
        except (asyncio.CancelledError, subprocess.TimeoutExpired):
            cleanup()
            await asyncio.gather(waiter, return_exceptions=True)
            await asyncio.to_thread(process.wait)
            raise
        else:
            cleanup()
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


class OpenCodeCLIProvider:
    """One-shot chat provider backed by ``opencode run``."""

    def __init__(self, model: str, timeout: float | None = None):
        self.model = model
        self.timeout = float(timeout or os.getenv("SYNAPSE_OPENCODE_TIMEOUT", DEFAULT_TIMEOUT))

    async def generate(
        self, prompt: str, *, selected_by_user: bool = False, cancellable: bool = False, **kwargs: Any,
    ) -> dict[str, Any]:
        if local_only_enabled() and not (
            selected_by_user and selected_opencode_enabled() and self.model.startswith("opencode/")
        ):
            raise RuntimeError("OpenCode can only be used for a model explicitly selected by the user")
        if is_opencode_quota_exhausted(self.model):
            state = quota_status(self.model)
            raise OpenCodeQuotaExceeded(
                "OpenCode free usage limit is exhausted"
                + (f" (retry in {state['retry_after_seconds']}s)" if state["retry_after_seconds"] else "")
                + ". Subscribe to OpenCode Go, configure another provider, or use the local model.",
                retry_after_seconds=state["retry_after_seconds"],
            )

        cli = await asyncio.to_thread(find_opencode_cli) if cancellable else find_opencode_cli()
        if cli is None:
            message = "OpenCode CLI was not found. Install OpenCode or set SYNAPSE_OPENCODE_CLI."
            record_opencode_failure(message, model_id=self.model)
            raise RuntimeError(message)

        if selected_by_user:
            models = await asyncio.to_thread(list_opencode_models) if cancellable else list_opencode_models()
            if self.model not in models:
                raise RuntimeError(f"The selected OpenCode model is absent from the catalog: {self.model}")

        env = opencode_child_environment()
        env["NO_COLOR"] = "1"
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            _merge_config_content(), ensure_ascii=False
        )
        workdir = tempfile.mkdtemp(prefix="synapse-opencode-")
        args = [
            str(cli),
            "run",
            "--standalone",
            "--format",
            "json",
            "--log-level",
            "none",
            "--archived",
            "--agent",
            _OPENCODE_AGENT,
            "--model",
            self.model,
            "--",
            prompt,
        ]
        try:
            options = dict(
                executable=str(cli),
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=workdir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if cancellable:
                completed = await _run_cancellable(args, self.timeout, **options)
            else:
                completed = await asyncio.to_thread(
                    subprocess.run, args, capture_output=True, timeout=self.timeout, **options,
                )
        except subprocess.TimeoutExpired as exc:
            message = f"OpenCode did not answer within {self.timeout:g}s for {self.model}"
            record_opencode_failure(message, model_id=self.model)
            raise RuntimeError(message) from exc
        except OSError as exc:
            message = f"OpenCode CLI could not be started: {exc}"
            record_opencode_failure(message, model_id=self.model)
            raise RuntimeError(message) from exc
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        texts, error = _parse_events(completed.stdout or "")
        content = "\n\n".join(texts).strip()
        if error:
            kind = record_opencode_failure(error, model_id=self.model)
            if kind == "quota":
                state = quota_status(self.model)
                raise OpenCodeQuotaExceeded(
                    f"{error} (retry in {state['retry_after_seconds']}s)"
                    if state["retry_after_seconds"] else str(error),
                    retry_after_seconds=state["retry_after_seconds"],
                )
            # An error event means the run failed even if some text was
            # streamed first. Returning that partial text would hide the
            # failure and leak runtime diagnostics into the chat answer.
            raise RuntimeError(error)
        if cancellable and completed.returncode != 0:
            raise RuntimeError(f"OpenCode exited with code {completed.returncode}.")
        content = _strip_quota_notice_lines(content)
        if content and _is_quota_notice(content):
            record_opencode_failure(content, model_id=self.model)
            state = quota_status(self.model)
            raise OpenCodeQuotaExceeded(
                "OpenCode free usage limit is exhausted"
                + (f" (retry in {state['retry_after_seconds']}s)" if state["retry_after_seconds"] else "")
                + ". Subscribe to OpenCode Go, configure another provider, or use the local model.",
                retry_after_seconds=state["retry_after_seconds"],
            )
        if not content:
            stderr = (completed.stderr or "").strip()
            suffix = f" stderr: {stderr[:400]}" if stderr else ""
            message = f"OpenCode returned no assistant text for {self.model}{suffix}"
            record_opencode_failure(message, model_id=self.model)
            raise RuntimeError(message)
        record_opencode_success(model_id=self.model)
        result = {
            "content": content,
            "provider": "opencode",
            "model": self.model,
            "usage": {},
        }
        if cancellable:
            types = {"step_finish", "tool_use"}
            events = []
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                kind = event.get("type") if isinstance(event, dict) else None
                if isinstance(kind, str) and kind in types:
                    events.append({"type": kind})
            result["events"] = tuple(events)
        return result


__all__ = ["OpenCodeCLIProvider", "OpenCodeQuotaExceeded"]
