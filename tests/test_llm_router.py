"""Tests for LLM router."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestLLMRouter:
    """Test LLM router."""

    @pytest.fixture
    def router(self):
        """Create an LLM router for testing."""
        from synapse.llm.router import LLMRouter

        router = LLMRouter()

        # Create mock providers
        primary = MagicMock()
        primary.name = "primary"
        primary.priority = 1
        primary.is_active = True
        primary.capabilities = ["chat"]
        primary.generate = AsyncMock(return_value={"text": "primary response"})

        fallback = MagicMock()
        fallback.name = "fallback"
        fallback.priority = 2
        fallback.is_active = True
        fallback.capabilities = ["chat"]
        fallback.generate = AsyncMock(return_value={"text": "fallback response"})

        safe = MagicMock()
        safe.name = "safe"
        safe.priority = 3
        safe.is_active = True
        safe.capabilities = ["chat"]
        safe.generate = AsyncMock(return_value={"text": "safe response"})

        router.register(primary)
        router.register(fallback)
        router.register(safe)
        router.set_safe_provider("safe")

        return router

    def test_router_creation(self, router):
        """Test router creation."""
        assert router is not None

    def test_protocol_version(self, router):
        """Test protocol version."""
        assert router.protocol_version == "1.0"

    def test_list_providers(self, router):
        """Test listing providers."""
        providers = router.list_providers()
        assert "primary" in providers
        assert "fallback" in providers
        assert "safe" in providers

    def test_select_provider(self, router):
        """Test selecting a provider."""
        provider = router.select_provider()
        assert provider.name == "primary"

    def test_select_provider_with_capability(self, router):
        """Test selecting a provider with capability."""
        provider = router.select_provider(required_capability="chat")
        assert provider is not None

    @pytest.mark.asyncio
    async def test_generate(self, router):
        """Test generating a response."""
        response = await router.generate("test prompt")
        assert response is not None
        assert "text" in response

    def test_create_prompt_envelope(self, router):
        """Test creating a prompt envelope."""
        envelope = router.create_prompt_envelope("test prompt")
        assert "prompt" in envelope
        assert "hash" in envelope
        assert "protocol_version" in envelope

    def test_set_timeout(self, router):
        """Test setting timeout."""
        router.set_timeout(60.0)
        assert router._timeout == 60.0
