"""LLM Provider Layer - Production Ready."""
from typing import Dict, Any, Optional, List
from enum import IntEnum
import asyncio
import hashlib
import json

PROTOCOL_VERSION: str = "1.0"


class LLMPriority(IntEnum):
    PRIMARY = 1
    FALLBACK = 2
    SAFE = 3


class LLMRouter:
    """Production LLM router with fallback and capability routing."""
    protocol_version: str = PROTOCOL_VERSION

    def __init__(self):
        self._providers: Dict[str, Any] = {}
        self._safe_provider_name: Optional[str] = None
        self._timeout: float = 30.0

    def register(self, provider: Any) -> None:
        """Register an LLM provider."""
        self._providers[provider.name] = provider

    def list_providers(self) -> List[str]:
        """List registered providers."""
        return list(self._providers.keys())

    def set_safe_provider(self, name: str) -> None:
        """Set the safe mode provider."""
        self._safe_provider_name = name

    def set_timeout(self, seconds: float) -> None:
        """Set timeout for LLM requests."""
        self._timeout = seconds

    def select_provider(self, required_capability: Optional[str] = None) -> Any:
        """Select provider based on priority and capabilities."""
        # Sort by priority (lower = higher priority)
        sorted_providers = sorted(
            self._providers.values(),
            key=lambda p: p.priority
        )

        for provider in sorted_providers:
            if not provider.is_active:
                continue
            if required_capability:
                if required_capability in provider.capabilities:
                    return provider
            else:
                return provider

        raise RuntimeError("No available provider")

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response with fallback handling."""
        sorted_providers = sorted(
            self._providers.values(),
            key=lambda p: p.priority
        )

        last_error = None

        for provider in sorted_providers:
            if not provider.is_active:
                continue

            try:
                result = await asyncio.wait_for(
                    provider.generate(prompt, **kwargs),
                    timeout=self._timeout
                )
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Provider {provider.name} timed out")
                continue
            except Exception as e:
                last_error = e
                continue

        # Use safe provider if all fail
        if self._safe_provider_name and self._safe_provider_name in self._providers:
            safe = self._providers[self._safe_provider_name]
            return await safe.generate(prompt, **kwargs)

        if last_error:
            raise last_error
        raise RuntimeError("No available provider")

    def create_prompt_envelope(self, prompt: str) -> Dict[str, Any]:
        """Create deterministic prompt envelope."""
        # Hash-based deterministic envelope
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        return {
            "prompt": prompt,
            "hash": prompt_hash,
            "protocol_version": self.protocol_version
        }
