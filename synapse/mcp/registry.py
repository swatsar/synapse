"""MCP Control Layer — Synapse-owned registry and policy boundary.

Synapse remains the single control plane for MCP servers. This module provides
a lightweight registry that tracks discovered MCP servers, their tool groups,
and permission bindings without reimplementing the MCP wire protocol (which is
delegated to the official SDK at runtime).

Reference: Hermes MCP discovery + WeKnora workspace-scoped MCP endpoints.
Clean-room implementation; no code copied from upstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

PROTOCOL_VERSION: str = "1.0"


class McpTransport(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


@dataclass(frozen=True, init=False)
class McpServerRecord:
    """Validated metadata for an MCP server.

    ``endpoint`` is retained for compatibility with existing callers. New code
    can use the transport-specific ``command``/``args`` and ``url`` fields.
    """

    id: str
    display_name: str
    transport: McpTransport
    endpoint: str
    args: tuple[str, ...]
    workspace_id: str | None
    tenant_id: str | None
    tool_groups: tuple[str, ...]
    permissions: tuple[str, ...]
    enabled: bool
    metadata: dict[str, Any]
    protocol_version: str

    def __init__(
        self,
        id: str,
        transport: McpTransport | str,
        endpoint: str | None = None,
        *,
        command: str | None = None,
        url: str | None = None,
        args: list[str] | tuple[str, ...] = (),
        display_name: str | None = None,
        workspace_id: str | None = None,
        tenant_id: str | None = None,
        tool_groups: list[str] | tuple[str, ...] = (),
        permissions: list[str] | tuple[str, ...] = (),
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> None:
        if not isinstance(id, str) or not id.strip():
            raise ValueError("MCP server id must be a non-empty string")
        try:
            transport = McpTransport(transport)
        except ValueError as exc:
            raise ValueError(f"Unsupported MCP transport: {transport}") from exc

        supplied = [value for value in (endpoint, command, url) if value is not None]
        if len(supplied) != 1:
            raise ValueError("Specify exactly one of endpoint, command, or url")
        if transport is McpTransport.STDIO and url is not None:
            raise ValueError("STDIO servers require command, not url")
        if transport is McpTransport.STREAMABLE_HTTP and command is not None:
            raise ValueError("HTTP servers require url, not command")
        if transport is McpTransport.STREAMABLE_HTTP and args:
            raise ValueError("HTTP servers do not accept command arguments")

        endpoint_value = supplied[0].strip()
        if not endpoint_value:
            raise ValueError("MCP endpoint must not be empty")
        if transport is McpTransport.STREAMABLE_HTTP:
            parsed = urlparse(endpoint_value)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError("MCP HTTP endpoint must be an absolute HTTP(S) URL")
        if any(not isinstance(arg, str) for arg in args):
            raise TypeError("MCP command arguments must be strings")

        object.__setattr__(self, "id", id.strip())
        object.__setattr__(self, "display_name", display_name or id.strip())
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "endpoint", endpoint_value)
        object.__setattr__(self, "args", tuple(args))
        object.__setattr__(self, "workspace_id", workspace_id)
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "tool_groups", tuple(tool_groups))
        object.__setattr__(self, "permissions", tuple(permissions))
        object.__setattr__(self, "enabled", enabled)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "protocol_version", protocol_version)

    @property
    def command(self) -> str | None:
        return self.endpoint if self.transport is McpTransport.STDIO else None

    @property
    def url(self) -> str | None:
        return self.endpoint if self.transport is McpTransport.STREAMABLE_HTTP else None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "display_name": self.display_name,
            "transport": self.transport.value,
            "endpoint": self.endpoint,
            "workspace_id": self.workspace_id,
            "tenant_id": self.tenant_id,
            "tool_groups": list(self.tool_groups),
            "permissions": list(self.permissions),
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
            "protocol_version": self.protocol_version,
        }
        if self.transport is McpTransport.STDIO:
            result.update(command=self.command, args=list(self.args))
        else:
            result["url"] = self.url
        return result


class McpRegistry:
    """In-process registry of MCP server records.

    The registry owns *metadata and policy* about MCP servers, not their
    runtime connections. Actual stdio/HTTP transports are managed by the
    official MCP SDK when a harness or tool invocation requests them.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self) -> None:
        self._servers: dict[str, McpServerRecord] = {}

    def register(self, record: McpServerRecord) -> McpServerRecord:
        self._servers[record.id] = record
        return record

    def unregister(self, server_id: str) -> bool:
        return self._servers.pop(server_id, None) is not None

    def get(self, server_id: str) -> McpServerRecord | None:
        return self._servers.get(server_id)

    def list(
        self,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        include_disabled: bool = False,
    ) -> list[McpServerRecord]:
        results: list[McpServerRecord] = []
        for rec in self._servers.values():
            if not include_disabled and not rec.enabled:
                continue
            if tenant_id is not None and rec.tenant_id not in (None, tenant_id):
                continue
            if workspace_id is not None and rec.workspace_id not in (None, workspace_id):
                continue
            results.append(rec)
        return results

    def resolve_tool_groups(self, server_id: str) -> tuple[str, ...]:
        rec = self._servers.get(server_id)
        return rec.tool_groups if rec else ()


__all__ = ["McpRegistry", "McpServerRecord", "McpTransport"]
