"""Synapse provider registry public API."""
from synapse.llm.providers.adapters import ConnectionResult, DiscoveredModel, get_adapter
from synapse.llm.providers.persistence import InMemoryProfileStore, JsonProfileStore, ProfileStore
from synapse.llm.providers.profile import ApiMode, AuthType, ModelCatalogSource, ProviderProfile
from synapse.llm.providers.registry import ProviderRegistry

__all__ = [
    "ApiMode", "AuthType", "ConnectionResult", "DiscoveredModel",
    "InMemoryProfileStore", "JsonProfileStore", "ModelCatalogSource",
    "ProfileStore", "ProviderProfile", "ProviderRegistry", "get_adapter",
]
