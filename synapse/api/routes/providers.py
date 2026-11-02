"""Provider onboarding API backed by Synapse's single ProviderRegistry.

The route keeps the legacy response shape for existing clients, but provider
state is owned by the registry and credentials are represented only by
secret:// references. Connection tests and model discovery are real adapter
operations; no fake success or hardcoded context windows are returned.
"""
from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from synapse.llm.catalog import ModelCatalog, descriptors_from_provider_models
from synapse.llm.credentials import SecretError, create_default_credential_store
from synapse.llm.providers import (
    ApiMode,
    AuthType,
    JsonProfileStore,
    ModelCatalogSource,
    ProviderProfile,
    ProviderRegistry,
)

PROTOCOL_VERSION: str = "1.0"
router = APIRouter()


class ProviderCreate(BaseModel):
    name: str
    api_key: str | None = None
    credential_ref: str | None = None
    models: list[str] = Field(default_factory=list)
    priority: int = 3
    base_url: str | None = None
    api_mode: ApiMode = ApiMode.OPENAI_COMPATIBLE
    auth_type: AuthType = AuthType.API_KEY
    tenant_id: str | None = None

    @model_validator(mode="after")
    def require_credential_input(self):
        if not self.api_key and not self.credential_ref:
            raise ValueError("api_key or credential_ref is required")
        return self


class ProviderUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    credential_ref: str | None = None
    models: list[str] | None = None
    priority: int | None = None
    base_url: str | None = None
    api_mode: ApiMode | None = None
    auth_type: AuthType | None = None
    tenant_id: str | None = None


class PriorityUpdate(BaseModel):
    priority: int


def _provider_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_")


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class ProviderService:
    """Compatibility facade over ProviderRegistry and ModelCatalog."""

    def __init__(self, registry: ProviderRegistry | None = None):
        if registry is None:
            config_path = Path(__file__).resolve().parents[3] / "config" / "providers.json"
            credentials = create_default_credential_store()
            registry = ProviderRegistry(JsonProfileStore(config_path), credentials)
        self.registry = registry
        self.catalog = ModelCatalog()
        self._priorities: dict[str, int] = {}

    async def list_providers(self) -> list[dict[str, Any]]:
        profiles = await self.registry.list(include_disabled=True)
        return [self._public(p) for p in profiles]

    async def get_provider(self, provider_id: str) -> dict[str, Any] | None:
        profile = await self.registry.get(provider_id)
        return self._public(profile) if profile else None

    async def create_provider(self, data: ProviderCreate) -> dict[str, Any]:
        provider_id = _provider_id(data.name)
        credential_ref = data.credential_ref
        # Legacy api_key input is accepted for compatibility but never written
        # to the provider record. Operators should use secret:// explicitly.
        if data.api_key and not credential_ref:
            credential_ref = f"secret://env/SYNAPSE_PROVIDER_{provider_id.upper()}_API_KEY"
        profile = ProviderProfile(
            id=provider_id,
            display_name=data.name,
            api_mode=data.api_mode,
            base_url=data.base_url,
            auth_type=data.auth_type,
            credential_ref=credential_ref,
            model_catalog_source=(ModelCatalogSource.MANUAL if data.models else ModelCatalogSource.PROVIDER_API),
            default_model=data.models[0] if data.models else None,
            fallback_models=data.models[1:],
            tenant_id=data.tenant_id,
            metadata={"legacy_models": list(data.models), "priority": data.priority},
        )
        await self.registry.register(profile)
        self._priorities[provider_id] = data.priority
        return self._public(profile)

    async def update_provider(self, provider_id: str, data: ProviderUpdate) -> dict[str, Any] | None:
        profile = await self.registry.get(provider_id)
        if profile is None:
            return None
        values = profile.to_public_dict()
        patch = data.model_dump(exclude_unset=True)
        if "name" in patch:
            values["display_name"] = patch.pop("name")
        patch.pop("api_key", None)
        values.update({k: v for k, v in patch.items() if v is not None})
        values["id"] = provider_id
        values["api_mode"] = values["api_mode"].value if isinstance(values["api_mode"], ApiMode) else values["api_mode"]
        values["auth_type"] = values["auth_type"].value if isinstance(values["auth_type"], AuthType) else values["auth_type"]
        values.pop("protocol_version", None)
        updated = ProviderProfile(**values)
        await self.registry.register(updated)
        return self._public(updated)

    async def delete_provider(self, provider_id: str) -> bool:
        return await self.registry.unregister(provider_id)

    async def test_connection(self, provider_id: str) -> dict[str, Any]:
        return (await self.registry.test_connection(provider_id)).to_dict()

    async def list_models(self, provider_id: str) -> list[dict[str, Any]]:
        discovered = await self.registry.discover_models(provider_id)
        descriptors = descriptors_from_provider_models(provider_id, discovered)
        self.catalog.merge(descriptors)
        if descriptors:
            return [d.to_dict() for d in descriptors]
        profile = await self.registry.get(provider_id)
        if profile is None:
            return []
        return [{"id": model, "display_name": model, "context_window": None,
                 "max_output": None, "capabilities": {}}
                for model in profile.metadata.get("legacy_models", [])]

    async def set_priority(self, provider_id: str, priority: int) -> dict[str, Any] | None:
        profile = await self.registry.get(provider_id)
        if profile is None:
            return None
        self._priorities[provider_id] = priority
        profile.metadata["priority"] = priority
        await self.registry.register(profile)
        return self._public(profile)

    def _public(self, profile: ProviderProfile) -> dict[str, Any]:
        data = profile.to_public_dict()
        data["name"] = profile.display_name
        data["models"] = list(profile.fallback_models) + ([profile.default_model] if profile.default_model else [])
        data["priority"] = self._priorities.get(profile.id, profile.metadata.get("priority", 3))
        return data


provider_service = ProviderService()


@router.get("")
async def list_providers():
    return {"providers": await _maybe_await(provider_service.list_providers()), "protocol_version": PROTOCOL_VERSION}


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    provider = await _maybe_await(provider_service.get_provider(provider_id))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("", status_code=201)
async def create_provider(data: ProviderCreate):
    return await _maybe_await(provider_service.create_provider(data))


@router.put("/{provider_id}")
async def update_provider(provider_id: str, data: ProviderUpdate):
    provider = await _maybe_await(provider_service.update_provider(provider_id, data))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: str):
    if not await _maybe_await(provider_service.delete_provider(provider_id)):
        raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/{provider_id}/test")
async def test_provider_connection(provider_id: str):
    return await _maybe_await(provider_service.test_connection(provider_id))


@router.get("/{provider_id}/models")
async def list_provider_models(provider_id: str):
    models = await _maybe_await(provider_service.list_models(provider_id))
    return {"models": models, "protocol_version": PROTOCOL_VERSION}


@router.patch("/{provider_id}/priority")
async def set_provider_priority(provider_id: str, data: PriorityUpdate):
    provider = await _maybe_await(provider_service.set_priority(provider_id, data.priority))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider
