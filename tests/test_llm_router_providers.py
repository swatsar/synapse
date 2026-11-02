"""Tests for LLM Provider Layer - Production Ready."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from enum import IntEnum


class LLMPriority(IntEnum):
    PRIMARY = 1
    FALLBACK = 2
    SAFE = 3


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    provider = MagicMock()
    provider.name = "test_provider"
    provider.priority = LLMPriority.PRIMARY
    provider.is_active = True
    provider.capabilities = ["chat", "completion"]
    provider.protocol_version = "1.0"
    provider.generate = AsyncMock(return_value={"text": "response", "protocol_version": "1.0"})
    return provider


@pytest.fixture
def fallback_provider():
    """Mock fallback LLM provider."""
    provider = MagicMock()
    provider.name = "fallback_provider"
    provider.priority = LLMPriority.FALLBACK
    provider.is_active = True
    provider.capabilities = ["chat"]
    provider.protocol_version = "1.0"
    provider.generate = AsyncMock(return_value={"text": "fallback response", "protocol_version": "1.0"})
    return provider


@pytest.fixture
def safe_provider():
    """Mock safe mode LLM provider."""
    provider = MagicMock()
    provider.name = "safe_provider"
    provider.priority = LLMPriority.SAFE
    provider.is_active = True
    provider.capabilities = ["chat"]
    provider.protocol_version = "1.0"
    provider.generate = AsyncMock(return_value={"text": "safe response", "protocol_version": "1.0"})
    return provider


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_registration(mock_provider):
    """Test LLM provider registration."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(mock_provider)
    
    assert "test_provider" in router.list_providers()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fallback_on_failure(mock_provider, fallback_provider):
    """Test fallback switching when primary fails."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(mock_provider)
    router.register(fallback_provider)
    
    # Primary fails
    mock_provider.generate.side_effect = Exception("Primary failed")
    
    result = await router.generate("test prompt")
    assert result["text"] == "fallback response"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deterministic_provider_selection(mock_provider, fallback_provider):
    """Test deterministic provider selection based on priority."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(fallback_provider)  # Lower priority
    router.register(mock_provider)  # Higher priority
    
    selected = router.select_provider()
    assert selected.name == "test_provider"  # Primary selected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_capability_based_routing(mock_provider, fallback_provider):
    """Test capability-based provider routing."""
    from synapse.llm.provider import LLMRouter
    
    mock_provider.capabilities = ["chat", "completion"]
    fallback_provider.capabilities = ["chat"]
    
    router = LLMRouter()
    router.register(mock_provider)
    router.register(fallback_provider)
    
    # Request requiring completion capability
    selected = router.select_provider(required_capability="completion")
    assert selected.name == "test_provider"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_safe_provider_on_all_failures(mock_provider, fallback_provider, safe_provider):
    """Test safe provider used when all others fail."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(mock_provider)
    router.register(fallback_provider)
    router.register(safe_provider)
    router.set_safe_provider("safe_provider")
    
    # All fail
    mock_provider.generate.side_effect = Exception("Failed")
    fallback_provider.generate.side_effect = Exception("Failed")
    
    result = await router.generate("test prompt")
    assert result["text"] == "safe response"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_version_in_requests(mock_provider):
    """Test protocol_version is included in requests."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(mock_provider)
    
    result = await router.generate("test prompt")
    assert "protocol_version" in result
    assert result["protocol_version"] == "1.0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_timeout_handling(mock_provider):
    """Test timeout handling for LLM requests."""
    from synapse.llm.provider import LLMRouter
    import asyncio
    
    router = LLMRouter()
    router.register(mock_provider)
    router.set_timeout(0.01)  # 10ms timeout
    
    # Simulate slow response
    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(1)
        return {"text": "response"}
    
    mock_provider.generate = slow_generate
    
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await router.generate("test prompt")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deterministic_prompt_envelope(mock_provider):
    """Test deterministic prompt envelope generation."""
    from synapse.llm.provider import LLMRouter
    
    router = LLMRouter()
    router.register(mock_provider)
    
    envelope1 = router.create_prompt_envelope("test prompt")
    envelope2 = router.create_prompt_envelope("test prompt")
    
    assert envelope1 == envelope2  # Same input = same envelope
    assert "protocol_version" in envelope1
