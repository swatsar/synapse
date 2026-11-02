"""ProviderProfile — declarative description of an LLM provider.

A profile describes *how to talk* to a provider (wire protocol, base URL, auth
shape) and *where its credentials live* (a secret:// reference), never the
credentials themselves. This mirrors the provider-plugin + ProviderProfile
split used by Hermes, adapted to Synapse's zero-trust credential store.

Reference: Hermes ProviderProfile (architectural idea, clean-room implementation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PROTOCOL_VERSION: str = "1.0"


class ApiMode(str, Enum):
    """Wire protocol used by a provider's generation endpoint.

    A separate adapter is only needed when the wire protocol genuinely differs;
    openai_compatible covers any endpoint speaking Chat Completions.
    """

    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GEMINI_NATIVE = "gemini_native"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    BEDROCK = "bedrock"
    VERTEX_AI = "vertex_ai"
    OPENAI_COMPATIBLE = "openai_compatible"
    CUSTOM_HTTP = "custom_http"


class AuthType(str, Enum):
    """How a provider authenticates a request."""

    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    NONE = "none"


class ModelCatalogSource(str, Enum):
    """Where a provider's model list comes from."""

    PROVIDER_API = "provider_api"
    PLUGIN_METADATA = "plugin_metadata"
    MANUAL = "manual"


@dataclass
class ProviderProfile:
    """Declarative provider description.

    Attributes:
        id: stable, unique provider id (e.g. "openrouter")
        display_name: human-readable label
        api_mode: wire protocol (see ApiMode)
        base_url: API root, provider-specific
        auth_type: authentication shape
        credential_ref: secret:// reference; never a raw key
        model_catalog_source: where models are discovered from
        capabilities: provider-level capabilities (e.g. "streaming", "reasoning")
        default_model: model id used when none is requested
        fallback_models: ordered fallback model ids
        enabled: whether the provider may be used
        tenant_id: owning tenant (None = shared/platform)
        metadata: free-form, non-secret extra data
    """

    id: str
    display_name: str
    api_mode: ApiMode = ApiMode.OPENAI_COMPATIBLE
    base_url: str | None = None
    auth_type: AuthType = AuthType.API_KEY
    credential_ref: str | None = None
    model_catalog_source: ModelCatalogSource = ModelCatalogSource.PROVIDER_API
    capabilities: list[str] = field(default_factory=list)
    default_model: str | None = None
    fallback_models: list[str] = field(default_factory=list)
    enabled: bool = True
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("provider id is required")
        if self.credential_ref is not None and not isinstance(self.credential_ref, str):
            raise ValueError("credential_ref must be a string secret:// reference")
        if isinstance(self.api_mode, str):
            self.api_mode = ApiMode(self.api_mode)
        if isinstance(self.auth_type, str):
            self.auth_type = AuthType(self.auth_type)
        if isinstance(self.model_catalog_source, str):
            self.model_catalog_source = ModelCatalogSource(self.model_catalog_source)

    def to_public_dict(self) -> dict[str, Any]:
        """Serialization that never contains credentials.

        credential_ref is included so operators can see *which* secret is bound,
        but the secret itself is only resolvable through the CredentialStore.
        """
        return {
            "id": self.id,
            "display_name": self.display_name,
            "api_mode": self.api_mode.value,
            "base_url": self.base_url,
            "auth_type": self.auth_type.value,
            "credential_ref": self.credential_ref,
            "model_catalog_source": self.model_catalog_source.value,
            "capabilities": list(self.capabilities),
            "default_model": self.default_model,
            "fallback_models": list(self.fallback_models),
            "enabled": self.enabled,
            "tenant_id": self.tenant_id,
            "protocol_version": self.protocol_version,
        }


__all__ = ["ApiMode", "AuthType", "ModelCatalogSource", "ProviderProfile"]
