"""Provider for models served by the local OpenCode runtime.

OpenCode is an agent runtime, not a plain chat-completions HTTP endpoint. This
provider runs its CLI in one-shot JSON mode with a Synapse-specific agent whose
tool permissions are denied, so a chat request returns assistant text without
editing the workspace. Discovery and quota state live in
``synapse.integrations.opencode_bridge``.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from synapse.integrations.opencode_bridge import (
    find_opencode_cli,
    is_opencode_quota_exhausted,
    quota_status,
    record_opencode_failure,
    record_opencode_success,
)

DEFAULT_TIMEOUT = 180.0
SYNAPSE_AGENT = "synapse-chat"


class OpenCodeQuotaExceeded(RuntimeError):
    """Raised when free OpenCode usage is exhausted and retrying is pointless."""

    def __init__(self, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = int(retry_after_seconds)


def _tool_denied_agent() -> dict[str, Any]:
    """Agent definition that can answer but cannot call tools."""
    return {
        "mode": "primary",
        "description": "Synapse chat: answer the user directly, without tools or workspace changes.",
        "steps": 2,
        "permissions": [{"action": "*", "resource": "*", "effect": "deny"}],
    }


def _merge_config_content(model_id: str) -> dict[str, Any]:
    """Preserve an existing OpenCode config while adding our tool-denied agent."""
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
        ]
    }
    agents = content.setdefault("agents", {})
    if isinstance(agents, dict):
        agents[SYNAPSE_AGENT] = _tool_denied_agent()
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


class OpenCodeCLIProvider:
    """One-shot chat provider backed by ``opencode run``."""

    def __init__(self, model: str, timeout: float | None = None):
        self.model = model
        self.timeout = float(timeout or os.getenv("SYNAPSE_OPENCODE_TIMEOUT", DEFAULT_TIMEOUT))

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if is_opencode_quota_exhausted():
            state = quota_status()
            raise OpenCodeQuotaExceeded(
                "OpenCode free usage limit is exhausted"
                + (f" (retry in {state['retry_after_seconds']}s)" if state["retry_after_seconds"] else "")
                + ". Subscribe to OpenCode Go, configure another provider, or use the local model.",
                retry_after_seconds=state["retry_after_seconds"],
            )

        cli = find_opencode_cli()
        if cli is None:
            message = "OpenCode CLI was not found. Install OpenCode or set SYNAPSE_OPENCODE_CLI."
            record_opencode_failure(message)
            raise RuntimeError(message)

        env = dict(os.environ)
        env["NO_COLOR"] = "1"
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            _merge_config_content(self.model), ensure_ascii=False
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
            "--agent",
            SYNAPSE_AGENT,
            "--model",
            self.model,
            prompt,
            workdir,
        ]
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
                cwd=workdir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            message = f"OpenCode did not answer within {self.timeout:g}s for {self.model}"
            record_opencode_failure(message)
            raise RuntimeError(message) from exc
        except OSError as exc:
            message = f"OpenCode CLI could not be started: {exc}"
            record_opencode_failure(message)
            raise RuntimeError(message) from exc
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        texts, error = _parse_events(completed.stdout or "")
        content = "\n\n".join(texts).strip()
        if error:
            kind = record_opencode_failure(error)
            if kind == "quota":
                state = quota_status()
                raise OpenCodeQuotaExceeded(
                    f"{error} (retry in {state['retry_after_seconds']}s)"
                    if state["retry_after_seconds"] else str(error),
                    retry_after_seconds=state["retry_after_seconds"],
                )
            # An error event means the run failed even if some text was
            # streamed first. Returning that partial text would hide the
            # failure and leak runtime diagnostics into the chat answer.
            raise RuntimeError(error)
        content = _strip_quota_notice_lines(content)
        if content and _is_quota_notice(content):
            record_opencode_failure(content)
            state = quota_status()
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
            record_opencode_failure(message)
            raise RuntimeError(message)
        record_opencode_success()
        return {
            "content": content,
            "provider": "opencode",
            "model": self.model,
            "usage": {},
        }


__all__ = ["OpenCodeCLIProvider", "OpenCodeQuotaExceeded"]
