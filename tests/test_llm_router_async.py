"""Async tests for LLM router."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestLLMRouterAsync:
    """Test LLM router async functionality."""
    
    @pytest.fixture
    def router(self):
        """Create an LLM router for testing."""
        from synapse.llm.router import LLMRouter
        return LLMRouter()
    
    @pytest.fixture
    def provider(self):
        """Create a mock provider."""
        provider = MagicMock()
        provider.name = "test_provider"
        provider.model = "test_model"
        provider.priority = 1
        provider.is_active = True
        provider.capabilities = ["chat", "completion"]
        provider.generate = AsyncMock(return_value={"text": "test response"})
        
        return provider
    
    @pytest.fixture
    def fallback_provider(self):
        """Create a fallback provider."""
        provider = MagicMock()
        provider.name = "fallback_provider"
        provider.model = "fallback_model"
        provider.priority = 2
        provider.is_active = True
        provider.capabilities = ["chat"]
        provider.generate = AsyncMock(return_value={"text": "fallback response"})
        
        return provider
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback(self, router, provider, fallback_provider):
        """Test generating a response with fallback."""
        router.register(provider)
        router.register(fallback_provider)
        
        # Make primary provider fail
        provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        
        response = await router.generate("test prompt")
        
        assert response == {"text": "fallback response"}
    
    @pytest.mark.asyncio
    async def test_generate_with_safe_provider(self, router, provider):
        """Test generating a response with safe provider."""
        router.register(provider)
        router.set_safe_provider("test_provider")
        
        # Make primary provider fail
        provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        
        # Reset the mock for safe provider call
        provider.generate = AsyncMock(return_value={"text": "safe response"})
        
        response = await router.generate("test prompt")
        
        assert response == {"text": "safe response"}
    
    @pytest.mark.asyncio
    async def test_generate_timeout(self, router, provider):
        """Test generating a response with timeout."""
        router.register(provider)
        router.set_timeout(0.1)
        
        # Make provider hang
        async def slow_generate(*args, **kwargs):
            import asyncio
            await asyncio.sleep(1)
            return {"text": "response"}
        
        provider.generate = slow_generate
        
        with pytest.raises(Exception):
            await router.generate("test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_no_provider(self, router):
        """Test generating a response with no provider."""
        with pytest.raises(RuntimeError):
            await router.generate("test prompt")
