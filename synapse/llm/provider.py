"""LLM Provider Layer — real litellm integration.

Protocol Version: 1.0
"""
import asyncio
import hashlib
import os
from enum import IntEnum
from typing import Any

PROTOCOL_VERSION: str = "1.0"


class EmbeddingUnavailable(RuntimeError):
    """No embedding backend could produce a vector.

    Raised instead of fabricating a pseudo-embedding (e.g. a hash digest):
    retrieval layers must fall back to lexical search honestly.
    """


class LLMPriority(IntEnum):
    PRIMARY = 1
    FALLBACK = 2
    SAFE = 3


class LiteLLMProvider:
    """Production LLM provider using litellm for multi-model support."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        priority: int = LLMPriority.PRIMARY,
        capabilities: list[str] | None = None,
    ):
        self.name = name
        self.model = model
        self.api_key = api_key or os.getenv(f"{name.upper()}_API_KEY", "")
        self.api_base = api_base
        self.priority = priority
        self.capabilities = capabilities or []
        self.is_active = True
        self.protocol_version = PROTOCOL_VERSION

    async def generate(self, prompt: str, **kwargs) -> dict[str, Any]:
        """Generate response via litellm."""
        try:
            import litellm

            messages = kwargs.pop("messages", None) or [{"role": "user", "content": prompt}]
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: litellm.completion(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key or None,
                    api_base=self.api_base or None,
                    **kwargs,
                ),
            )
            content = response.choices[0].message.content or ""
            return {
                "content": content,
                "model": self.model,
                "usage": dict(response.usage) if response.usage else {},
                "protocol_version": PROTOCOL_VERSION,
            }
        except ImportError as exc:
            raise RuntimeError(
                f"LLM backend unavailable ({self.model}): litellm is not installed"
            ) from exc
        except Exception as e:
            raise RuntimeError(f"LLM call failed ({self.model}): {e}") from e

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings via litellm.

        Raises:
            EmbeddingUnavailable: when no embedding backend can serve the
                request. A cryptographic hash digest is deliberately *not*
                used as a stand-in: hashes carry no semantic similarity signal
                and silently poison downstream retrieval. Callers must degrade
                to lexical retrieval (BM25/FTS) instead.
        """
        try:
            import litellm
        except ImportError as exc:
            raise EmbeddingUnavailable(
                "litellm is not installed; no embedding backend available"
            ) from exc

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: litellm.embedding(
                    model=self.model,
                    input=[text],
                    api_key=self.api_key or None,
                ),
            )
            return list(response.data[0]["embedding"])
        except Exception as exc:
            raise EmbeddingUnavailable(
                f"embedding backend unavailable for model {self.model}: {exc}"
            ) from exc


class LLMRouter:
    """Production LLM router with fallback and capability routing."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self):
        self._providers: dict[str, LiteLLMProvider] = {}
        self._safe_provider_name: str | None = None
        self._timeout: float = 30.0

    def register(self, provider: LiteLLMProvider) -> None:
        self._providers[provider.name] = provider

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def set_safe_provider(self, name: str) -> None:
        self._safe_provider_name = name

    def set_timeout(self, seconds: float) -> None:
        self._timeout = seconds

    def select_provider(self, required_capability: str | None = None) -> LiteLLMProvider:
        sorted_providers = sorted(self._providers.values(), key=lambda p: p.priority)
        for provider in sorted_providers:
            if not provider.is_active:
                continue
            if required_capability and required_capability not in provider.capabilities:
                continue
            return provider
        raise RuntimeError("No available LLM provider")

    async def generate(self, prompt: str, **kwargs) -> dict[str, Any]:
        """Generate with automatic fallback across providers."""
        sorted_providers = sorted(self._providers.values(), key=lambda p: p.priority)
        last_error = None
        for provider in sorted_providers:
            if not provider.is_active:
                continue
            try:
                return await asyncio.wait_for(
                    provider.generate(prompt, **kwargs),
                    timeout=self._timeout,
                )
            except TimeoutError:
                last_error = TimeoutError(f"Provider {provider.name} timed out")
            except Exception as e:
                last_error = e
        if self._safe_provider_name and self._safe_provider_name in self._providers:
            return await self._providers[self._safe_provider_name].generate(prompt, **kwargs)
        raise last_error or RuntimeError("No available provider")

    def create_prompt_envelope(self, prompt: str) -> dict[str, Any]:
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        return {"prompt": prompt, "hash": prompt_hash, "protocol_version": self.protocol_version}


def create_default_router() -> LLMRouter:
    """Create a router pre-loaded with environment-configured providers."""
    router = LLMRouter()
    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        router.register(LiteLLMProvider("openai", "gpt-4o", priority=LLMPriority.PRIMARY))
    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        router.register(LiteLLMProvider("anthropic", "claude-sonnet-5-5", priority=LLMPriority.FALLBACK))
    # Google
    if os.getenv("GOOGLE_API_KEY"):
        router.register(LiteLLMProvider("google", "gemini-1.5-pro", priority=LLMPriority.FALLBACK))
    # Ollama (local)
    if os.getenv("OLLAMA_API_BASE"):
        router.register(LiteLLMProvider(
            "ollama", "ollama/llama3.2",
            api_base=os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
            priority=LLMPriority.SAFE,
        ))
    return router
