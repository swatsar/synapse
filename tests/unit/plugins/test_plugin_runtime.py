import pytest

from synapse.plugins import PluginLifecycle, PluginManifest, PluginPermission, PluginRuntime
from synapse.plugins.manifest import DependencyError, ManifestValidationError


def manifest(**kwargs):
    values = dict(id="p.one", version="1.0.0", kind="tool", provides=("tool.one",),
                  permissions=(PluginPermission.WORKSPACE.value,))
    values.update(kwargs)
    return PluginManifest(**values)


def test_manifest_rejects_unknown_permission_and_fields():
    with pytest.raises(ManifestValidationError):
        manifest(permissions=("unlimited",))
    with pytest.raises(ManifestValidationError):
        PluginManifest.from_dict({"id":"x", "version":"1", "kind":"tool", "provides":["x"], "unknown":1})


def test_manifest_permission_diff():
    diff = manifest(permissions=("workspace", "network:example.com")).permission_diff({"workspace"})
    assert diff == {"added": ["network:example.com"], "unchanged": ["workspace"], "removed": []}

@pytest.mark.asyncio
async def test_runtime_dependency_order_and_service_registration():
    runtime = PluginRuntime(granted_permissions={"workspace"})
    runtime.discover(manifest(id="base", provides=("base.service",)))
    runtime.discover(manifest(id="child", dependencies=("base",), provides=("child.service",)))
    loaded = []
    async def loader(m):
        loaded.append(m.id)
        return {m.provides[0]: m.id}
    record = await runtime.activate("child", loader)
    assert record.state is PluginLifecycle.ACTIVE
    assert loaded == ["base", "child"]
    assert runtime.services == {"base.service":"base", "child.service":"child"}

@pytest.mark.asyncio
async def test_runtime_blocks_unapproved_permissions():
    runtime = PluginRuntime()
    record = runtime.discover(manifest())
    result = await runtime.activate("p.one", AsyncLoader())
    assert result.state is PluginLifecycle.SUSPENDED
    assert "permissions require approval" in result.error

class AsyncLoader:
    def __call__(self, manifest):
        async def inner():
            return {}
        return inner()

@pytest.mark.asyncio
async def test_runtime_detects_missing_dependency_and_cycles():
    runtime = PluginRuntime(granted_permissions={"workspace"})
    runtime.discover(manifest(id="a", dependencies=("missing",)))
    with pytest.raises(DependencyError):
        await runtime.validate("a")
    runtime = PluginRuntime(granted_permissions={"workspace"})
    runtime.discover(manifest(id="a", dependencies=("b",)))
    runtime.discover(manifest(id="b", dependencies=("a",)))
    with pytest.raises(DependencyError):
        await runtime.validate("a")

@pytest.mark.asyncio
async def test_runtime_deactivate_disposes_services():
    runtime = PluginRuntime(granted_permissions={"workspace"})
    runtime.discover(manifest())
    async def loader(m): return {"tool.one": object()}
    await runtime.activate("p.one", loader)
    disposed = []
    async def disposer(m): disposed.append(m.id)
    record = await runtime.deactivate("p.one", disposer)
    assert record.state is PluginLifecycle.DISPOSED
    assert disposed == ["p.one"]
    assert "tool.one" not in runtime.services
