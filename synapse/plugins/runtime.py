"""Small, explicit plugin lifecycle runtime owned by Synapse."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from synapse.plugins.manifest import DependencyError, PluginLifecycle, PluginManifest, PluginRecord


class PluginRuntime:
    """Manage plugin records, dependencies, services, and permissions.

    Loading is callback-driven so the runtime does not invent an agent loop or
    scheduler. A host supplies the actual plugin loader and unload callbacks.
    """

    def __init__(self, granted_permissions: set[str] | None = None):
        self.records: dict[str, PluginRecord] = {}
        self.services: dict[str, Any] = {}
        self.granted_permissions = set(granted_permissions or ())

    def discover(self, manifest: PluginManifest) -> PluginRecord:
        if manifest.id in self.records:
            raise DependencyError(f"plugin already discovered: {manifest.id}")
        record = PluginRecord(manifest=manifest)
        self.records[manifest.id] = record
        return record

    def permission_diff(self, plugin_id: str) -> dict[str, list[str]]:
        return self.records[plugin_id].manifest.permission_diff(self.granted_permissions)

    def _topological_order(self, plugin_id: str) -> list[str]:
        if plugin_id not in self.records:
            raise DependencyError(f"unknown plugin: {plugin_id}")
        order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(current: str) -> None:
            if current in visiting:
                raise DependencyError(f"dependency cycle involving {current}")
            if current in visited:
                return
            visiting.add(current)
            for dependency in self.records[current].manifest.dependencies:
                if dependency not in self.records:
                    raise DependencyError(f"missing dependency {dependency} for {current}")
                visit(dependency)
            visiting.remove(current)
            visited.add(current)
            order.append(current)

        visit(plugin_id)
        return order

    async def validate(self, plugin_id: str) -> PluginRecord:
        record = self.records[plugin_id]
        self._topological_order(plugin_id)
        missing = set(record.manifest.permissions) - self.granted_permissions
        if missing:
            record.state = PluginLifecycle.SUSPENDED
            record.error = f"permissions require approval: {sorted(missing)}"
        else:
            record.state = PluginLifecycle.VALIDATED
            record.error = None
        return record

    async def activate(self, plugin_id: str, loader: Callable[[PluginManifest], Awaitable[dict[str, Any] | None]]) -> PluginRecord:
        order = self._topological_order(plugin_id)
        for current in order:
            record = await self.validate(current)
            if record.state is PluginLifecycle.SUSPENDED:
                return record
            record.state = PluginLifecycle.LOADING
            try:
                provided = await loader(record.manifest) or {}
                for service, implementation in provided.items():
                    self.services[service] = implementation
                record.state = PluginLifecycle.ACTIVE
                record.error = None
            except Exception as exc:
                record.state = PluginLifecycle.FAILED
                record.error = str(exc)
                raise
        return self.records[plugin_id]

    async def deactivate(self, plugin_id: str, disposer: Callable[[PluginManifest], Awaitable[None]] | None = None) -> PluginRecord:
        record = self.records[plugin_id]
        record.state = PluginLifecycle.STOPPING
        if disposer is not None:
            await disposer(record.manifest)
        for service in record.manifest.provides:
            self.services.pop(service, None)
        record.state = PluginLifecycle.DISPOSED
        return record

    def list(self, state: PluginLifecycle | None = None) -> list[PluginRecord]:
        records = self.records.values()
        if state is not None:
            records = (r for r in records if r.state is state)
        return list(records)
