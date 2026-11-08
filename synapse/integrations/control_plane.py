"""Persistent, non-secret control-plane state for operator-managed integrations."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from synapse.mcp import McpRegistry, McpServerRecord
from synapse.plugins import PluginLifecycle, PluginManifest, PluginRecord


_SECRET_KEYS = {"api_key", "apikey", "authorization", "password", "secret", "token", "credential"}


def _assert_non_secret(payload: dict[str, Any]) -> None:
    """Reject secret-bearing integration declarations before persistence."""
    for key, value in payload.items():
        normalized = str(key).lower().replace("-", "_")
        if normalized in _SECRET_KEYS or any(part in normalized for part in _SECRET_KEYS):
            raise ValueError(f"secret-bearing field is not allowed: {key}")
        if isinstance(value, dict):
            _assert_non_secret(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    _assert_non_secret(item)
    for key in ("endpoint", "url"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if parsed.username or parsed.password:
            raise ValueError("secret-bearing credentials are not allowed in MCP URLs")
        if any(name.lower().replace("-", "_") in _SECRET_KEYS for name, _ in parse_qsl(parsed.query)):
            raise ValueError("secret-bearing credential query parameters are not allowed")


def _root() -> Path:
    root = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).expanduser().resolve()
    path = root / ".synapse" / "integrations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(name: str, default: Any) -> Any:
    path = _root() / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(name: str, value: Any) -> None:
    path = _root() / name
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class IntegrationControlPlane:
    """Store integration declarations, never credentials or executable output."""

    def list_mcp(self, *, include_disabled: bool = True) -> list[McpServerRecord]:
        registry = McpRegistry()
        for payload in _read("mcp_servers.json", []) or []:
            try:
                registry.register(McpServerRecord(**payload))
            except (TypeError, ValueError):
                continue
        return registry.list(include_disabled=include_disabled)

    def upsert_mcp(self, payload: dict[str, Any]) -> McpServerRecord:
        _assert_non_secret(payload)
        record = McpServerRecord(**payload)
        records = [item.to_dict() for item in self.list_mcp(include_disabled=True) if item.id != record.id]
        records.append(record.to_dict())
        _write("mcp_servers.json", records)
        return record

    def delete_mcp(self, server_id: str) -> bool:
        records = self.list_mcp(include_disabled=True)
        remaining = [item for item in records if item.id != server_id]
        if len(remaining) == len(records):
            return False
        _write("mcp_servers.json", [item.to_dict() for item in remaining])
        return True

    def list_plugins(self) -> list[PluginRecord]:
        result: list[PluginRecord] = []
        for payload in _read("plugins.json", []) or []:
            try:
                manifest = PluginManifest.from_dict(payload["manifest"])
                state = PluginLifecycle(payload.get("state", PluginLifecycle.DISCOVERED.value))
                result.append(PluginRecord(manifest=manifest, state=state, error=payload.get("error")))
            except (KeyError, TypeError, ValueError):
                continue
        return result

    def upsert_plugin(self, payload: dict[str, Any]) -> PluginRecord:
        _assert_non_secret(payload)
        manifest = PluginManifest.from_dict(payload)
        records = [item for item in self.list_plugins() if item.id != manifest.id]
        record = PluginRecord(manifest=manifest, state=PluginLifecycle.DISCOVERED)
        records.append(record)
        _write("plugins.json", [{"manifest": item.manifest.to_dict(), "state": item.state.value, "error": item.error} for item in records])
        return record

    def set_plugin_state(self, plugin_id: str, state: PluginLifecycle, error: str | None = None) -> PluginRecord | None:
        records = self.list_plugins()
        target = next((item for item in records if item.id == plugin_id), None)
        if target is None:
            return None
        target.state = state
        target.error = error
        _write("plugins.json", [{"manifest": item.manifest.to_dict(), "state": item.state.value, "error": item.error} for item in records])
        return target

    def executor_config(self) -> dict[str, Any]:
        payload = _read("executors.json", {})
        return payload if isinstance(payload, dict) else {}

    def update_executor(self, executor_id: str, *, enabled: bool | None = None, write_enabled: bool | None = None, timeout_seconds: float | None = None, command: list[str] | None = None) -> dict[str, Any]:
        config = self.executor_config()
        current = dict(config.get(executor_id, {}))
        if enabled is not None:
            current["enabled"] = bool(enabled)
        if write_enabled is not None:
            current["write_enabled"] = bool(write_enabled)
        if timeout_seconds is not None:
            current["timeout_seconds"] = float(timeout_seconds)
        if command is not None:
            if not command or not all(isinstance(item, str) and item.strip() for item in command):
                raise ValueError("command must be a non-empty argv list of strings")
            current["command"] = [item.strip() for item in command]
        config[executor_id] = current
        _write("executors.json", config)
        return current


def get_control_plane() -> IntegrationControlPlane:
    return IntegrationControlPlane()


__all__ = ["IntegrationControlPlane", "get_control_plane"]

