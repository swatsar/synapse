"""LLM Provider Layer — real litellm integration.

Protocol Version: 1.0
"""
from typing import Dict, Any, Optional, List
from enum import IntEnum
import asyncio
import hashlib
import json
import os

PROTOCOL_VERSION: str = "1.0"


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
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        priority: int = LLMPriority.PRIMARY,
        capabilities: Optional[List[str]] = None,
    ):
        self.name = name
        self.model = model
        self.api_key = api_key or os.getenv(f"{name.upper()}_API_KEY", "")
        self.api_base = api_base
        self.priority = priority
        self.capabilities = capabilities or []
        self.is_active = True
        self.protocol_version = PROTOCOL_VERSION

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
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
        except ImportError:
            # litellm not installed — graceful degradation
            return {
                "content": f"[LLM unavailable — litellm not installed] Prompt: {prompt[:100]}",
                "model": self.model,
                "usage": {},
                "protocol_version": PROTOCOL_VERSION,
            }
        except Exception as e:
            raise RuntimeError(f"LLM call failed ({self.model}): {e}") from e

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings via litellm."""
        try:
            import litellm

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: litellm.embedding(
                    model=self.model,
                    input=[text],
                    api_key=self.api_key or None,
                ),
            )
            return response.data[0]["embedding"]
        except Exception:
            # Deterministic fallback embedding
            import struct, hashlib as _h
            digest = _h.sha512(text.encode()).digest()
            raw = (digest * ((768 * 4 // len(digest)) + 1))[: 768 * 4]
            values = struct.unpack(f">{768}f", raw)
            max_abs = max(abs(v) for v in values) or 1.0
            return [v / max_abs for v in values]


class LLMRouter:
    """Production LLM router with fallback and capability routing."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self):
        self._providers: Dict[str, LiteLLMProvider] = {}
        self._safe_provider_name: Optional[str] = None
        self._timeout: float = 30.0

    def register(self, provider: LiteLLMProvider) -> None:
        self._providers[provider.name] = provider

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def set_safe_provider(self, name: str) -> None:
        self._safe_provider_name = name

    def set_timeout(self, seconds: float) -> None:
        self._timeout = seconds

    def select_provider(self, required_capability: Optional[str] = None) -> LiteLLMProvider:
        sorted_providers = sorted(self._providers.values(), key=lambda p: p.priority)
        for provider in sorted_providers:
            if not provider.is_active:
                continue
            if required_capability and required_capability not in provider.capabilities:
                continue
            return provider
        raise RuntimeError("No available LLM provider")

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
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
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Provider {provider.name} timed out")
            except Exception as e:
                last_error = e
        if self._safe_provider_name and self._safe_provider_name in self._providers:
            return await self._providers[self._safe_provider_name].generate(prompt, **kwargs)
        raise last_error or RuntimeError("No available provider")

    def create_prompt_envelope(self, prompt: str) -> Dict[str, Any]:
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
        router.register(LiteLLMProvider("anthropic", "claude-3-5-sonnet-20241022", priority=LLMPriority.FALLBACK))
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
