"""Tests for LLM Router edge cases."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import asyncio


class TestLLMRouterEdgeCases:
    """Test LLM Router edge cases for full coverage."""
    
    @pytest.fixture
    def llm_router(self):
        """Create an LLMRouter."""
        from synapse.llm.router import LLMRouter
        
        return LLMRouter()
    
    @pytest.fixture
    def mock_provider_no_capability(self):
        """Create a mock LLM provider without specific capability."""
        provider = MagicMock()
        provider.name = "no_capability_provider"
        provider.priority = 1
        provider.is_active = True
        provider.capabilities = ["other"]
        provider.generate = AsyncMock(return_value={"text": "test response"})
        return provider
    
    @pytest.fixture
    def mock_provider_with_capability(self):
        """Create a mock LLM provider with specific capability."""
        provider = MagicMock()
        provider.name = "capability_provider"
        provider.priority = 2
        provider.is_active = True
        provider.capabilities = ["chat", "special"]
        provider.generate = AsyncMock(return_value={"text": "special response"})
        return provider
    
    @pytest.fixture
    def mock_safe_provider(self):
        """Create a mock safe LLM provider."""
        provider = MagicMock()
        provider.name = "safe_provider"
        provider.priority = 3
        provider.is_active = True
        provider.capabilities = ["safe"]
        provider.generate = AsyncMock(return_value={"text": "safe response"})
        return provider
    
    def test_select_provider_capability_not_in_provider(self, llm_router, mock_provider_no_capability, mock_provider_with_capability):
        """Test select_provider when first provider doesn't have capability."""
        llm_router.register(mock_provider_no_capability)
        llm_router.register(mock_provider_with_capability)
        
        selected = llm_router.select_provider(required_capability="special")
        
        # Should skip the first provider and return the second one
        assert selected.name == "capability_provider"
    
    def test_select_provider_no_capability_match(self, llm_router, mock_provider_no_capability):
        """Test select_provider when no provider has the required capability."""
        llm_router.register(mock_provider_no_capability)
        
        with pytest.raises(RuntimeError):
            llm_router.select_provider(required_capability="nonexistent")
    
    @pytest.mark.asyncio
    async def test_generate_timeout_fallback(self, llm_router, mock_provider_no_capability, mock_provider_with_capability):
        """Test generate with timeout fallback."""
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            return {"text": "test response"}
        
        mock_provider_no_capability.generate = slow_generate
        llm_router.register(mock_provider_no_capability)
        llm_router.register(mock_provider_with_capability)
        llm_router.set_timeout(0.1)
        
        result = await llm_router.generate("test prompt")
        
        # Should fallback to the second provider
        assert result["text"] == "special response"
    
    @pytest.mark.asyncio
    async def test_generate_safe_provider_fallback(self, llm_router, mock_provider_no_capability, mock_safe_provider):
        """Test generate with safe provider fallback."""
        mock_provider_no_capability.generate = AsyncMock(side_effect=Exception("Primary failed"))
        llm_router.register(mock_provider_no_capability)
        llm_router.register(mock_safe_provider)
        llm_router.set_safe_provider("safe_provider")
        
        result = await llm_router.generate("test prompt")
        
        assert result["text"] == "safe response"
    
    @pytest.mark.asyncio
    async def test_generate_all_providers_inactive(self, llm_router, mock_provider_no_capability):
        """Test generate when all providers are inactive."""
        mock_provider_no_capability.is_active = False
        llm_router.register(mock_provider_no_capability)
        
        with pytest.raises(RuntimeError):
            await llm_router.generate("test prompt")
