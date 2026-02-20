"""Full tests for LLM router."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestLLMRouterFull:
    """Test LLM router comprehensively."""
    
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
    
    def test_router_creation(self, router):
        """Test router creation."""
        assert router is not None
    
    def test_protocol_version(self, router):
        """Test protocol version."""
        assert router.protocol_version == "1.0"
    
    def test_register(self, router, provider):
        """Test registering a provider."""
        router.register(provider)
        
        assert "test_provider" in router._providers
    
    def test_list_providers(self, router, provider):
        """Test listing providers."""
        router.register(provider)
        
        providers = router.list_providers()
        
        assert "test_provider" in providers
    
    def test_set_safe_provider(self, router, provider):
        """Test setting safe provider."""
        router.register(provider)
        router.set_safe_provider("test_provider")
        
        assert router._safe_provider_name == "test_provider"
    
    def test_set_timeout(self, router):
        """Test setting timeout."""
        router.set_timeout(60.0)
        
        assert router._timeout == 60.0
    
    def test_select_provider(self, router, provider):
        """Test selecting a provider."""
        router.register(provider)
        
        selected = router.select_provider()
        
        assert selected == provider
    
    def test_select_provider_with_capability(self, router, provider):
        """Test selecting a provider with capability."""
        router.register(provider)
        
        selected = router.select_provider(required_capability="chat")
        
        assert selected == provider
    
    @pytest.mark.asyncio
    async def test_generate(self, router, provider):
        """Test generating a response."""
        router.register(provider)
        
        response = await router.generate("test prompt")
        
        assert response == {"text": "test response"}
    
    def test_create_prompt_envelope(self, router):
        """Test creating prompt envelope."""
        envelope = router.create_prompt_envelope("test prompt")
        
        assert "prompt" in envelope
        assert "hash" in envelope
        assert "protocol_version" in envelope
