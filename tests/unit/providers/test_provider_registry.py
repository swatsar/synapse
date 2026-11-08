import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from synapse.llm.credentials.backends import EnvironmentSecretBackend
from synapse.llm.credentials.store import CredentialStore
from synapse.llm.providers import (
    ApiMode, AuthType, InMemoryProfileStore, JsonProfileStore, ProviderProfile,
    ProviderRegistry,
)
from synapse.llm.providers.adapters import (
    ConnectionResult,
    DiscoveredModel,
    OpenAICompatibleAdapter,
    UnsupportedProtocolAdapter,
    get_adapter,
)

def profile(**kwargs):
    values = dict(id="acme", display_name="Acme", base_url="https://acme.test/v1",
                  credential_ref="secret://env/ACME_KEY")
    values.update(kwargs)
    return ProviderProfile(**values)


def store_with_env(value="secret"):
    credentials = CredentialStore()
    credentials.register_backend(EnvironmentSecretBackend({"ACME_KEY": value}), make_default=True)
    return credentials


def test_profile_requires_stable_id_and_serializes_only_reference():
    p = profile()
    public = p.to_public_dict()
    assert public["credential_ref"] == "secret://env/ACME_KEY"
    assert "live-key" not in json.dumps(public)
    assert p.api_mode is ApiMode.OPENAI_COMPATIBLE
    assert p.auth_type is AuthType.API_KEY

@pytest.mark.asyncio
async def test_registry_register_get_list_and_tenant_isolation():
    registry = ProviderRegistry(InMemoryProfileStore())
    await registry.register(profile())
    await registry.register(profile(id="private", tenant_id="tenant-a", display_name="Private"))
    assert (await registry.get("acme", tenant_id="other")).id == "acme"
    assert await registry.get("private", tenant_id="other") is None
    assert [p.id for p in await registry.list(tenant_id="tenant-a")] == ["acme", "private"]
    assert [p.id for p in await registry.list(tenant_id="other")] == ["acme"]

@pytest.mark.asyncio
async def test_registry_json_store_roundtrip(tmp_path):
    path = tmp_path / "providers.json"
    store = JsonProfileStore(path)
    await store.save(profile())
    loaded = await store.load_all()
    assert loaded[0].id == "acme"
    assert loaded[0].credential_ref == "secret://env/ACME_KEY"
    assert "live-key" not in path.read_text()
    assert await store.delete("acme") is True
    assert await store.load_all() == []

@pytest.mark.asyncio
async def test_registry_resolves_credentials_without_storing_secret():
    registry = ProviderRegistry(InMemoryProfileStore(), store_with_env("live-key"))
    await registry.register(profile())
    secret = await registry.resolve_credential(profile())
    assert secret.reveal() == "live-key"

@pytest.mark.asyncio
async def test_connection_missing_provider_is_structured_failure():
    registry = ProviderRegistry(InMemoryProfileStore())
    result = await registry.test_connection("missing")
    assert result.success is False
    assert result.error == "provider_not_found"

@pytest.mark.asyncio
async def test_connection_uses_adapter_and_credential(monkeypatch):
    registry = ProviderRegistry(InMemoryProfileStore(), store_with_env("live-key"))
    await registry.register(profile())
    expected = ConnectionResult(True, latency_ms=4.2, model="acme-model")
    with patch("synapse.llm.providers.registry.get_adapter") as factory:
        factory.return_value.test_connection = AsyncMock(return_value=expected)
        result = await registry.test_connection("acme")
    assert result is expected
    factory.return_value.test_connection.assert_awaited_once_with("https://acme.test/v1", "live-key", timeout=15.0)

@pytest.mark.asyncio
async def test_discovery_uses_adapter_and_returns_models():
    registry = ProviderRegistry(InMemoryProfileStore(), store_with_env())
    await registry.register(profile())
    models = [DiscoveredModel("acme-model", context_window=8192)]
    with patch("synapse.llm.providers.registry.get_adapter") as factory:
        factory.return_value.discover_models = AsyncMock(return_value=models)
        result = await registry.discover_models("acme")
    assert result == models

@pytest.mark.asyncio
async def test_openai_adapter_probe_and_discovery():
    adapter = OpenAICompatibleAdapter()
    response = type("Response", (), {
        "status_code": 200,
        "json": lambda self: {"data": [{"id": "m1", "context_length": 4096}]},
        "raise_for_status": lambda self: None,
    })()
    client = AsyncMock()
    client.__aenter__.return_value.get = AsyncMock(return_value=response)
    client.__aexit__.return_value = False
    with patch.object(adapter, "_client", return_value=client):
        result = await adapter.test_connection("https://x/v1", "key")
        assert result.success is True
        models = await adapter.discover_models("https://x/v1", "key")
    assert models[0].id == "m1"
    assert models[0].context_window == 4096


def test_unsupported_api_mode_fails_closed_without_openai_probe():
    adapter = get_adapter(ApiMode.ANTHROPIC_MESSAGES)
    assert isinstance(adapter, UnsupportedProtocolAdapter)


async def test_unsupported_api_mode_returns_structured_failure_without_secret_lookup():
    registry = ProviderRegistry(InMemoryProfileStore())
    await registry.register(profile(api_mode=ApiMode.GEMINI_NATIVE))
    result = await registry.test_connection("acme")
    assert result.success is False
    assert result.error == "unsupported_api_mode"
    assert result.detail == {"api_mode": "gemini_native"}


def test_model_descriptor_has_explicit_capabilities_and_no_name_inference():
    from synapse.llm.catalog import CatalogSource, ModelCapabilities, ModelDescriptor
    descriptor = ModelDescriptor(
        id="reasoning-x", provider_id="acme", context_window=128000,
        capabilities=ModelCapabilities(reasoning=True, tool_calling=True,
                                        structured_output=True,
                                        reasoning_efforts=("low", "high")),
        source=CatalogSource.PLUGIN_METADATA,
    )
    data = descriptor.to_dict()
    assert data["capabilities"]["reasoning"] is True
    assert data["capabilities"]["reasoning_efforts"] == ["low", "high"]
    assert data["source"] == "plugin_metadata"


def test_model_catalog_upsert_is_provider_scoped():
    from synapse.llm.catalog import ModelCatalog, ModelDescriptor
    catalog = ModelCatalog()
    catalog.upsert(ModelDescriptor(id="same", provider_id="a"))
    catalog.upsert(ModelDescriptor(id="same", provider_id="b"))
    assert catalog.get("a", "same") is not None
    assert catalog.get("b", "same") is not None
    assert len(catalog.list()) == 2


def test_discovery_conversion_preserves_unknown_metadata_without_fabrication():
    from synapse.llm.catalog import descriptors_from_provider_models
    models = [DiscoveredModel("m1", context_window=None, raw={"owned_by": "acme"})]
    descriptor = descriptors_from_provider_models("acme", models)[0]
    assert descriptor.context_window is None
    assert descriptor.metadata == {"owned_by": "acme"}
