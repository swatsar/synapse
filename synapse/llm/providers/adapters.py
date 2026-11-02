"""Wire-protocol adapters for provider ApiModes.

Each adapter knows how to turn a Synapse request into a call against a specific
wire protocol, and how to list models from that protocol. openai_compatible is
the common case; the others exist only where the wire protocol genuinely
differs. Transport is delegated to litellm where it already speaks the
protocol, so we do not reimplement HTTP clients per provider.

Reference: DeepSeek Harness separates custom endpoints by API protocol rather
than assuming every base_url is Chat Completions (architectural idea,
clean-room implementation).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from synapse.llm.providers.profile import ApiMode

PROTOCOL_VERSION: str = "1.0"


@dataclass
class ConnectionResult:
    """Outcome of a real connection probe."""

    success: bool
    latency_ms: float | None = None
    model: str | None = None
    error: str | None = None
    detail: dict[str, Any] | None = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "error": self.error,
            "detail": self.detail or {},
            "protocol_version": self.protocol_version,
        }


@dataclass
class DiscoveredModel:
    """A model advertised by a provider endpoint."""

    id: str
    display_name: str | None = None
    context_window: int | None = None
    max_output: int | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name or self.id,
            "context_window": self.context_window,
            "max_output": self.max_output,
        }


class ProtocolAdapter(ABC):
    """Translates between Synapse semantics and one wire protocol."""

    api_mode: ApiMode = ApiMode.OPENAI_COMPATIBLE

    @abstractmethod
    async def test_connection(
        self, base_url: str | None, api_key: str | None, timeout: float = 15.0
    ) -> ConnectionResult:
        """Probe the provider with a real request (never a fake success)."""

    @abstractmethod
    async def discover_models(
        self, base_url: str | None, api_key: str | None, timeout: float = 30.0
    ) -> list[DiscoveredModel]:
        """List models the provider exposes, empty list on failure."""

    async def generate(self, model: str, messages: list[dict[str, Any]],
                       base_url: str | None, api_key: str | None,
                       **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class OpenAICompatibleAdapter(ProtocolAdapter):
    """Chat Completions over HTTP — the common case for custom providers."""

    api_mode = ApiMode.OPENAI_COMPATIBLE

    def _models_url(self, base_url: str | None) -> str:
        if not base_url:
            return "https://api.openai.com/v1"
        return base_url.rstrip("/").removesuffix("/chat/completions")

    def _client(self, api_key: str | None, timeout: float):
        import httpx

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        return httpx.AsyncClient(timeout=timeout, headers=headers)

    async def test_connection(self, base_url: str | None, api_key: str | None,
                              timeout: float = 15.0) -> ConnectionResult:
        import time

        url = f"{self._models_url(base_url)}/models"
        start = time.perf_counter()
        try:
            async with self._client(api_key, timeout) as client:
                response = await client.get(url)
            latency = (time.perf_counter() - start) * 1000
            if response.status_code == 401:
                return ConnectionResult(False, latency_ms=latency,
                                        error="authentication_failed",
                                        detail={"status": 401})
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            model_id = None
            if isinstance(data, list) and data:
                first = data[0]
                model_id = first.get("id") if isinstance(first, dict) else None
            return ConnectionResult(True, latency_ms=round(latency, 1), model=model_id)
        except Exception as exc:  # noqa: BLE001 - probe must report, not raise
            latency = (time.perf_counter() - start) * 1000
            return ConnectionResult(False, latency_ms=round(latency, 1),
                                    error=type(exc).__name__,
                                    detail={"message": str(exc)[:200]})

    async def discover_models(self, base_url: str | None, api_key: str | None,
                              timeout: float = 30.0) -> list[DiscoveredModel]:
        url = f"{self._models_url(base_url)}/models"
        try:
            async with self._client(api_key, timeout) as client:
                response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", []) if isinstance(payload, dict) else payload
            if not isinstance(data, list):
                return []
            models: list[DiscoveredModel] = []
            for item in data:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                models.append(
                    DiscoveredModel(
                        id=item["id"],
                        display_name=item.get("name") or item["id"],
                        context_window=item.get("context_length")
                        or item.get("context_window"),
                        max_output=item.get("max_output_tokens")
                        or item.get("max_output"),
                        raw=item,
                    )
                )
            return models
        except Exception:  # noqa: BLE001 - discovery failure = empty list
            return []

    async def generate(self, model: str, messages: list[dict[str, Any]],
                       base_url: str | None, api_key: str | None,
                       **kwargs: Any) -> dict[str, Any]:
        import litellm

        return await litellm.acompletion(  # type: ignore[attr-defined]
            model=model, messages=messages, api_base=base_url, api_key=api_key,
            **kwargs,
        )


class OllamaAdapter(OpenAICompatibleAdapter):
    """Ollama speaks an OpenAI-compatible /v1 surface plus its own /api."""

    api_mode = ApiMode.OLLAMA

    def _models_url(self, base_url: str | None) -> str:
        root = (base_url or "http://localhost:11434").rstrip("/")
        return root.removesuffix("/v1")

    async def discover_models(self, base_url: str | None, api_key: str | None,
                              timeout: float = 30.0) -> list[DiscoveredModel]:
        import httpx

        root = self._models_url(base_url)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{root}/api/tags")
            response.raise_for_status()
            data = response.json().get("models", [])
            return [
                DiscoveredModel(id=m.get("name", ""), display_name=m.get("name"),
                                raw=m)
                for m in data if isinstance(m, dict)
            ]
        except Exception:  # noqa: BLE001
            return await super().discover_models(base_url, api_key, timeout)


_ADAPTERS: dict[ApiMode, type[ProtocolAdapter]] = {
    ApiMode.OPENAI_COMPATIBLE: OpenAICompatibleAdapter,
    ApiMode.OPENAI_CHAT: OpenAICompatibleAdapter,
    ApiMode.OLLAMA: OllamaAdapter,
}


def get_adapter(api_mode: ApiMode | str) -> ProtocolAdapter:
    """Return the adapter for an ApiMode.

    Modes without a dedicated adapter (anthropic_messages, gemini_native,
    bedrock, vertex_ai, azure_openai) are handled by litellm's native transport
    and share the OpenAI-compatible probe for connection testing.
    """
    mode = ApiMode(api_mode) if isinstance(api_mode, str) else api_mode
    adapter_cls = _ADAPTERS.get(mode, OpenAICompatibleAdapter)
    return adapter_cls()


__all__ = [
    "ConnectionResult",
    "DiscoveredModel",
    "OpenAICompatibleAdapter",
    "OllamaAdapter",
    "ProtocolAdapter",
    "get_adapter",
]
