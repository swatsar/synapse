"""Pluggable persistence for provider profiles.

The registry itself keeps profiles in memory for fast lookups; a ProfileStore
is the durable source of truth and can be swapped for a database-backed
implementation without touching the registry.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from synapse.llm.providers.profile import ProviderProfile

logger = logging.getLogger(__name__)

PROTOCOL_VERSION: str = "1.0"


class ProfileStore(ABC):
    """Durable storage for provider profiles."""

    @abstractmethod
    async def load_all(self) -> list[ProviderProfile]: ...

    @abstractmethod
    async def save(self, profile: ProviderProfile) -> None: ...

    @abstractmethod
    async def delete(self, provider_id: str) -> bool: ...


class InMemoryProfileStore(ProfileStore):
    """Simple store for tests and single-process deployments."""

    def __init__(self) -> None:
        self._profiles: dict[str, ProviderProfile] = {}

    async def load_all(self) -> list[ProviderProfile]:
        return list(self._profiles.values())

    async def save(self, profile: ProviderProfile) -> None:
        self._profiles[profile.id] = profile

    async def delete(self, provider_id: str) -> bool:
        return self._profiles.pop(provider_id, None) is not None


class JsonProfileStore(ProfileStore):
    """JSON-file backed store (config/providers.json)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def load_all(self) -> list[ProviderProfile]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("provider store unreadable (%s): %s", self._path, exc)
            return []
        profiles: list[ProviderProfile] = []
        for item in data.get("providers", []):
            try:
                profiles.append(ProviderProfile(**item))
            except (TypeError, ValueError) as exc:
                logger.warning("skipping malformed provider entry: %s", exc)
        return profiles

    async def save(self, profile: ProviderProfile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = {p.id: p for p in await self.load_all()}
        existing[profile.id] = profile
        payload: dict[str, Any] = {
            "providers": [p.to_public_dict() for p in existing.values()],
            "protocol_version": PROTOCOL_VERSION,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    async def delete(self, provider_id: str) -> bool:
        existing = {p.id: p for p in await self.load_all()}
        if provider_id not in existing:
            return False
        del existing[provider_id]
        payload: dict[str, Any] = {
            "providers": [p.to_public_dict() for p in existing.values()],
            "protocol_version": PROTOCOL_VERSION,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True


__all__ = ["InMemoryProfileStore", "JsonProfileStore", "ProfileStore"]
