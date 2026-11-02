"""Model catalog and capability descriptors.

The catalog is provider-neutral: descriptors can come from a provider /models
endpoint, plugin metadata, or an explicit operator override. No routing code
needs to infer capabilities from model names.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from synapse.llm.pricing import ModelPricing

PROTOCOL_VERSION = "1.0"


class CatalogSource(str, Enum):
    PROVIDER_API = "provider_api"
    PLUGIN_METADATA = "plugin_metadata"
    MANUAL = "manual"


@dataclass(frozen=True)
class ModelCapabilities:
    modalities: frozenset[str] = frozenset({"text"})
    tool_calling: bool = False
    parallel_tools: bool = False
    reasoning: bool = False
    reasoning_efforts: tuple[str, ...] = ()
    structured_output: bool = False
    prompt_cache: bool = False
    computer_use: bool = False
    embeddings: bool = False
    streaming: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "modalities": sorted(self.modalities),
            "tool_calling": self.tool_calling,
            "parallel_tools": self.parallel_tools,
            "reasoning": self.reasoning,
            "reasoning_efforts": list(self.reasoning_efforts),
            "structured_output": self.structured_output,
            "prompt_cache": self.prompt_cache,
            "computer_use": self.computer_use,
            "embeddings": self.embeddings,
            "streaming": self.streaming,
        }


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    provider_id: str
    display_name: str | None = None
    context_window: int | None = None
    max_output: int | None = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    pricing: ModelPricing | None = None
    source: CatalogSource = CatalogSource.PROVIDER_API
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not self.id or not self.provider_id:
            raise ValueError("model id and provider_id are required")
        if self.context_window is not None and self.context_window <= 0:
            raise ValueError("context_window must be positive")
        if self.max_output is not None and self.max_output <= 0:
            raise ValueError("max_output must be positive")
        if isinstance(self.source, str):
            object.__setattr__(self, "source", CatalogSource(self.source))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "display_name": self.display_name or self.id,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "capabilities": self.capabilities.to_dict(),
            "pricing": self.pricing.to_dict() if self.pricing else None,
            "source": self.source.value,
            "metadata": dict(self.metadata),
            "protocol_version": self.protocol_version,
        }


class ModelCatalog:
    """Single in-process index of the durable model catalog."""

    def __init__(self, descriptors: Iterable[ModelDescriptor] = ()):
        self._models: dict[tuple[str, str], ModelDescriptor] = {}
        for descriptor in descriptors:
            self.upsert(descriptor)

    def upsert(self, descriptor: ModelDescriptor) -> ModelDescriptor:
        self._models[(descriptor.provider_id, descriptor.id)] = descriptor
        return descriptor

    def get(self, provider_id: str, model_id: str) -> ModelDescriptor | None:
        return self._models.get((provider_id, model_id))

    def list(self, provider_id: str | None = None) -> list[ModelDescriptor]:
        values = self._models.values()
        if provider_id is not None:
            values = (m for m in values if m.provider_id == provider_id)
        return sorted(values, key=lambda m: (m.provider_id, m.id))

    def merge(self, descriptors: Iterable[ModelDescriptor]) -> int:
        count = 0
        for descriptor in descriptors:
            self.upsert(descriptor)
            count += 1
        return count

    def remove_provider(self, provider_id: str) -> int:
        keys = [key for key in self._models if key[0] == provider_id]
        for key in keys:
            del self._models[key]
        return len(keys)

    def to_dict(self) -> dict[str, Any]:
        return {"models": [m.to_dict() for m in self.list()], "protocol_version": PROTOCOL_VERSION}


def descriptors_from_provider_models(provider_id: str, models: Iterable[Any]) -> list[ModelDescriptor]:
    """Convert adapter discovery results without inventing context metadata."""
    result = []
    for model in models:
        result.append(ModelDescriptor(
            id=model.id,
            provider_id=provider_id,
            display_name=getattr(model, "display_name", None),
            context_window=getattr(model, "context_window", None),
            max_output=getattr(model, "max_output", None),
            source=CatalogSource.PROVIDER_API,
            metadata=getattr(model, "raw", None) or {},
        ))
    return result


__all__ = ["CatalogSource", "ModelCapabilities", "ModelCatalog", "ModelDescriptor", "descriptors_from_provider_models"]
