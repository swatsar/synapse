"""Comprehensive tests for LLM router."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestLLMRouterComprehensive:
    """Test LLM router comprehensively."""
    
    @pytest.fixture
    def router(self):
        """Create an LLM router for testing."""
        from synapse.llm.router import LLMRouter
        
        router = LLMRouter()
        return router
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.name = "test_provider"
        provider.priority = 1
        provider.is_active = True
        provider.capabilities = []
        provider.generate = AsyncMock(return_value={"response": "test response"})
        return provider
    
    @pytest.fixture
    def mock_provider2(self):
        """Create a second mock LLM provider."""
        provider = MagicMock()
        provider.name = "fallback_provider"
        provider.priority = 2
        provider.is_active = True
        provider.capabilities = []
        provider.generate = AsyncMock(return_value={"response": "fallback response"})
        return provider
    
    def test_router_creation(self, router):
        """Test router creation."""
        assert router is not None
    
    def test_protocol_version(self, router):
        """Test protocol version."""
        assert router.protocol_version == "1.0"
    
    def test_register_provider(self, router, mock_provider):
        """Test registering a provider."""
        router.register(mock_provider)
        
        assert "test_provider" in router._providers
    
    def test_list_providers(self, router, mock_provider):
        """Test listing providers."""
        router.register(mock_provider)
        
        providers = router.list_providers()
        
        assert "test_provider" in providers
    
    def test_select_provider(self, router, mock_provider):
        """Test selecting a provider."""
        router.register(mock_provider)
        
        selected = router.select_provider()
        
        assert selected.name == "test_provider"
    
    @pytest.mark.asyncio
    async def test_generate(self, router, mock_provider):
        """Test generating a response."""
        router.register(mock_provider)
        
        response = await router.generate("test prompt")
        
        assert response["response"] == "test response"
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback(self, router, mock_provider, mock_provider2):
        """Test generating a response with fallback."""
        # Make primary provider fail
        mock_provider.generate = AsyncMock(side_effect=Exception("Primary failed"))
        
        router.register(mock_provider)
        router.register(mock_provider2)
        
        response = await router.generate("test prompt")
        
        assert response["response"] == "fallback response"
    
    def test_set_safe_provider(self, router, mock_provider):
        """Test setting safe provider."""
        router.register(mock_provider)
        router.set_safe_provider("test_provider")
        
        assert router._safe_provider_name == "test_provider"
    
    def test_set_timeout(self, router):
        """Test setting timeout."""
        router.set_timeout(60.0)
        
        assert router._timeout == 60.0
    
    def test_create_prompt_envelope(self, router):
        """Test creating prompt envelope."""
        envelope = router.create_prompt_envelope("test prompt")
        
        assert "prompt" in envelope
        assert "hash" in envelope
        assert "protocol_version" in envelope
        assert envelope["protocol_version"] == "1.0"
