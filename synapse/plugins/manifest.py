"""Synapse plugin manifest and lifecycle contracts.

Plugins extend Synapse through declared services and permissions. The runtime
owns lifecycle and dependency ordering; plugins never become a second control
plane or bypass CapabilityManager.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

PROTOCOL_VERSION = "1.0"


class PluginError(RuntimeError):
    pass


class ManifestValidationError(PluginError):
    pass


class DependencyError(PluginError):
    pass


class PluginLifecycle(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    INSTALLED = "installed"
    LOADING = "loading"
    ACTIVE = "active"
    STOPPING = "stopping"
    DISPOSED = "disposed"
    FAILED = "failed"
    SUSPENDED = "suspended"


class PluginPermission(str, Enum):
    NETWORK = "network"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    BROWSER = "browser"
    COMPUTER = "computer"
    SHELL = "shell"
    SECRETS = "secrets"
    DATABASE = "database"
    MCP = "mcp"
    WORKSPACE = "workspace"


@dataclass(frozen=True)
class PluginManifest:
    id: str
    version: str
    kind: str
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    entrypoint: str | None = None
    dependencies: tuple[str, ...] = ()
    publisher: str | None = None
    signature: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not self.id or not self.version or not self.kind:
            raise ManifestValidationError("plugin id, version, and kind are required")
        for permission in self.permissions:
            if permission not in {p.value for p in PluginPermission} and not permission.startswith("network:"):
                raise ManifestValidationError(f"unknown plugin permission: {permission}")
        if not self.provides:
            raise ManifestValidationError("plugin must declare at least one provided service")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        allowed = {"id", "version", "kind", "provides", "requires", "permissions",
                   "entrypoint", "dependencies", "publisher", "signature", "metadata",
                   "protocol_version"}
        unknown = set(data) - allowed
        if unknown:
            raise ManifestValidationError(f"unknown manifest fields: {sorted(unknown)}")
        values = dict(data)
        for key in ("provides", "requires", "permissions", "dependencies"):
            values[key] = tuple(values.get(key, ()))
        return cls(**values)

    @classmethod
    def from_yaml(cls, path: str) -> "PluginManifest":
        import yaml
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ManifestValidationError("manifest root must be an object")
        return cls.from_dict(data)

    def permission_diff(self, granted: Iterable[str]) -> dict[str, list[str]]:
        current = set(granted)
        requested = set(self.permissions)
        return {"added": sorted(requested - current), "unchanged": sorted(requested & current),
                "removed": sorted(current - requested)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "version": self.version, "kind": self.kind,
            "provides": list(self.provides), "requires": list(self.requires),
            "permissions": list(self.permissions), "entrypoint": self.entrypoint,
            "dependencies": list(self.dependencies), "publisher": self.publisher,
            "signature": self.signature, "metadata": dict(self.metadata),
            "protocol_version": self.protocol_version,
        }


@dataclass
class PluginRecord:
    manifest: PluginManifest
    state: PluginLifecycle = PluginLifecycle.DISCOVERED
    error: str | None = None

    @property
    def id(self) -> str:
        return self.manifest.id


__all__ = ["DependencyError", "ManifestValidationError", "PluginError", "PluginLifecycle", "PluginManifest", "PluginPermission", "PluginRecord"]
