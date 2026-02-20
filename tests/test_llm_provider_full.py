"""Tests for LLM Provider with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestLLMProviderFull:
    """Test LLM Provider with full coverage."""
    
    @pytest.fixture
    def llm_router(self):
        """Create an LLMRouter."""
        from synapse.llm.provider import LLMRouter
        
        return LLMRouter()
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.name = "test_provider"
        provider.priority = 1
        provider.is_active = True
        provider.capabilities = ["chat", "completion"]
        provider.generate = AsyncMock(return_value={"text": "test response"})
        return provider
    
    @pytest.fixture
    def mock_fallback_provider(self):
        """Create a mock fallback LLM provider."""
        provider = MagicMock()
        provider.name = "fallback_provider"
        provider.priority = 2
        provider.is_active = True
        provider.capabilities = ["chat"]
        provider.generate = AsyncMock(return_value={"text": "fallback response"})
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
    
    def test_llm_router_creation(self, llm_router):
        """Test LLMRouter creation."""
        assert llm_router is not None
        assert llm_router.protocol_version == "1.0"
    
    def test_register_provider(self, llm_router, mock_provider):
        """Test register provider."""
        llm_router.register(mock_provider)
        
        assert "test_provider" in llm_router.list_providers()
    
    def test_list_providers(self, llm_router, mock_provider, mock_fallback_provider):
        """Test list providers."""
        llm_router.register(mock_provider)
        llm_router.register(mock_fallback_provider)
        
        providers = llm_router.list_providers()
        
        assert len(providers) == 2
        assert "test_provider" in providers
        assert "fallback_provider" in providers
    
    def test_set_safe_provider(self, llm_router, mock_safe_provider):
        """Test set safe provider."""
        llm_router.register(mock_safe_provider)
        llm_router.set_safe_provider("safe_provider")
        
        assert llm_router._safe_provider_name == "safe_provider"
    
    def test_set_timeout(self, llm_router):
        """Test set timeout."""
        llm_router.set_timeout(60.0)
        
        assert llm_router._timeout == 60.0
    
    def test_select_provider(self, llm_router, mock_provider, mock_fallback_provider):
        """Test select provider."""
        llm_router.register(mock_provider)
        llm_router.register(mock_fallback_provider)
        
        selected = llm_router.select_provider()
        
        assert selected.name == "test_provider"
    
    def test_select_provider_with_capability(self, llm_router, mock_provider, mock_fallback_provider):
        """Test select provider with capability."""
        llm_router.register(mock_provider)
        llm_router.register(mock_fallback_provider)
        
        selected = llm_router.select_provider(required_capability="chat")
        
        assert selected.name == "test_provider"
    
    def test_select_provider_no_available(self, llm_router):
        """Test select provider no available."""
        with pytest.raises(RuntimeError):
            llm_router.select_provider()
    
    def test_select_provider_inactive(self, llm_router, mock_provider):
        """Test select provider inactive."""
        mock_provider.is_active = False
        llm_router.register(mock_provider)
        
        with pytest.raises(RuntimeError):
            llm_router.select_provider()
    
    @pytest.mark.asyncio
    async def test_generate(self, llm_router, mock_provider):
        """Test generate."""
        llm_router.register(mock_provider)
        
        result = await llm_router.generate("test prompt")
        
        assert result["text"] == "test response"
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback(self, llm_router, mock_provider, mock_fallback_provider):
        """Test generate with fallback."""
        mock_provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        llm_router.register(mock_provider)
        llm_router.register(mock_fallback_provider)
        
        result = await llm_router.generate("test prompt")
        
        assert result["text"] == "fallback response"
    
    @pytest.mark.asyncio
    async def test_generate_with_safe_provider(self, llm_router, mock_provider, mock_safe_provider):
        """Test generate with safe provider."""
        mock_provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        mock_safe_provider.generate = AsyncMock(return_value={"text": "safe response"})
        llm_router.register(mock_provider)
        llm_router.register(mock_safe_provider)
        llm_router.set_safe_provider("safe_provider")
        
        result = await llm_router.generate("test prompt")
        
        assert result["text"] == "safe response"
    
    @pytest.mark.asyncio
    async def test_generate_timeout(self, llm_router, mock_provider):
        """Test generate timeout."""
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            return {"text": "test response"}
        
        mock_provider.generate = slow_generate
        llm_router.register(mock_provider)
        llm_router.set_timeout(0.1)
        
        with pytest.raises((TimeoutError, RuntimeError)):
            await llm_router.generate("test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_all_fail(self, llm_router, mock_provider, mock_fallback_provider):
        """Test generate all fail."""
        mock_provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        mock_fallback_provider.generate = AsyncMock(side_effect=Exception("Fallback failed"))
        llm_router.register(mock_provider)
        llm_router.register(mock_fallback_provider)
        
        with pytest.raises(Exception):
            await llm_router.generate("test prompt")
    
    def test_create_prompt_envelope(self, llm_router):
        """Test create prompt envelope."""
        envelope = llm_router.create_prompt_envelope("test prompt")
        
        assert "prompt" in envelope
        assert "hash" in envelope
        assert "protocol_version" in envelope
        assert envelope["prompt"] == "test prompt"
        assert envelope["protocol_version"] == "1.0"
