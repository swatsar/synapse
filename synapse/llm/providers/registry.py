"""Provider Registry — the single catalog of LLM providers.

Synapse owns provider configuration. The registry is the only place providers
are registered, looked up (with tenant isolation), and bound to credentials.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from synapse.llm.credentials.protocol import SecretError, SecretValue
from synapse.llm.credentials.store import CredentialStore
from synapse.llm.providers.adapters import (
    ConnectionResult,
    DiscoveredModel,
    UnsupportedProtocolAdapter,
    get_adapter,
)
from synapse.llm.providers.circuit_breaker import CircuitBreaker, calculate_backoff
from synapse.llm.providers.persistence import InMemoryProfileStore, ProfileStore
from synapse.llm.providers.profile import ProviderProfile

logger = logging.getLogger(__name__)

PROTOCOL_VERSION: str = "1.0"


class ProviderRegistry:
    """Registry of provider profiles with tenant isolation and hot reload."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, store: ProfileStore | None = None,
                 credentials: CredentialStore | None = None):
        self._store: ProfileStore = store or InMemoryProfileStore()
        self._credentials = credentials
        self._profiles: dict[str, ProviderProfile] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._loaded = False

    def get_circuit_breaker(self, provider_id: str) -> CircuitBreaker:
        """Get or initialize circuit breaker for specified provider."""
        pid = provider_id.lower()
        if pid not in self._circuit_breakers:
            self._circuit_breakers[pid] = CircuitBreaker(
                name=pid,
                failure_threshold=5,
                recovery_timeout_sec=30.0,
            )
        return self._circuit_breakers[pid]

    async def _ensure_loaded(self) -> None:
        if not self._loaded:
            await self.reload()

    async def reload(self) -> None:
        """Re-read profiles from the durable store (hot reload)."""
        self._profiles = {p.id: p for p in await self._store.load_all()}
        self._loaded = True
        logger.info("provider registry reloaded: %d profile(s)", len(self._profiles))

    async def register(self, profile: ProviderProfile) -> ProviderProfile:
        await self._store.save(profile)
        self._profiles[profile.id] = profile
        return profile

    async def unregister(self, provider_id: str) -> bool:
        removed = await self._store.delete(provider_id)
        self._profiles.pop(provider_id, None)
        return removed

    async def get(self, provider_id: str, tenant_id: str | None = None) -> ProviderProfile | None:
        await self._ensure_loaded()
        profile = self._profiles.get(provider_id)
        if profile is None:
            return None
        if not _tenant_can_see(profile, tenant_id):
            return None
        return profile

    async def list(self, tenant_id: str | None = None,
                   include_disabled: bool = False) -> list[ProviderProfile]:
        await self._ensure_loaded()
        return [
            p for p in self._profiles.values()
            if (include_disabled or p.enabled) and _tenant_can_see(p, tenant_id)
        ]

    async def resolve_credential(self, profile: ProviderProfile) -> SecretValue:
        """Resolve a profile's credential_ref through the CredentialStore."""
        if self._credentials is None:
            raise SecretError("no credential store configured")
        if not profile.credential_ref:
            raise SecretError(f"provider {profile.id} has no credential_ref")
        return await self._credentials.resolve(profile.credential_ref)

    async def test_connection(self, provider_id: str, tenant_id: str | None = None,
                              timeout: float = 15.0, retries: int = 1) -> ConnectionResult:
        """Probe a provider with a real request using resolved credentials, guarded by circuit breaker."""
        cb = self.get_circuit_breaker(provider_id)
        if not cb.allow_request():
            return ConnectionResult(
                False,
                error="circuit_breaker_open",
                detail={"retry_after_sec": cb.time_until_retry()},
            )

        profile = await self.get(provider_id, tenant_id=tenant_id)
        if profile is None:
            return ConnectionResult(False, error="provider_not_found")

        adapter = get_adapter(profile.api_mode)
        if isinstance(adapter, UnsupportedProtocolAdapter):
            return await adapter.test_connection(profile.base_url, None, timeout=timeout)

        api_key = None
        if profile.credential_ref and self._credentials is not None:
            try:
                api_key = (await self.resolve_credential(profile)).reveal()
            except SecretError as exc:
                return ConnectionResult(False, error="credential_unavailable",
                                        detail={"message": str(exc)})
        last_res: ConnectionResult | None = None
        for attempt in range(1, max(1, retries) + 1):
            try:
                last_res = await adapter.test_connection(profile.base_url, api_key, timeout=timeout)
                if last_res.success:
                    cb.record_success()
                    return last_res
            except Exception as exc:
                last_res = ConnectionResult(False, error=str(exc))
            if attempt < retries:
                await asyncio.sleep(calculate_backoff(attempt))

        if last_res is not None:
            cb.record_failure(last_res.error)
            return last_res
        cb.record_failure("test_connection_failed")
        return ConnectionResult(False, error="test_connection_failed")

    async def discover_models(self, provider_id: str, tenant_id: str | None = None,
                              timeout: float = 30.0) -> list[DiscoveredModel]:
        """List models the provider actually exposes."""
        profile = await self.get(provider_id, tenant_id=tenant_id)
        if profile is None:
            return []
        api_key = None
        if profile.credential_ref and self._credentials is not None:
            try:
                api_key = (await self.resolve_credential(profile)).reveal()
            except SecretError as exc:
                logger.warning("cannot resolve credentials for %s: %s", provider_id, exc)
                return []
        adapter = get_adapter(profile.api_mode)
        return await adapter.discover_models(profile.base_url, api_key, timeout=timeout)

    def to_public_dict(self, tenant_id: str | None = None) -> dict[str, Any]:
        profiles = [p for p in self._profiles.values()
                    if _tenant_can_see(p, tenant_id)]
        providers_out = []
        for p in profiles:
            p_dict = p.to_public_dict()
            cb = self.get_circuit_breaker(p.id)
            p_dict["circuit_breaker"] = cb.get_stats().to_dict()
            providers_out.append(p_dict)
        return {
            "providers": providers_out,
            "protocol_version": self.protocol_version,
        }


def _tenant_can_see(profile: ProviderProfile, tenant_id: str | None) -> bool:
    """A tenant-scoped profile is visible only to its tenant; shared ones to all."""
    if profile.tenant_id is None:
        return True
    return profile.tenant_id == tenant_id


__all__ = ["ProviderRegistry"]
