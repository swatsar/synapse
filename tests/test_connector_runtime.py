"""Tests for Real Connector Runtime."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for connector tests."""
    orchestrator = MagicMock()
    orchestrator.handle = AsyncMock(return_value={"status": "completed", "response": "test response"})
    return orchestrator


@pytest.fixture
def mock_capability_manager():
    """Mock capability manager."""
    cap_manager = MagicMock()
    cap_manager.check = AsyncMock(return_value=True)
    return cap_manager


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    logger = MagicMock()
    logger.record = MagicMock()
    return logger


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connector_event_ingestion(mock_orchestrator):
    """Test incoming message → orchestrator → response flow."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator)
    
    event = {
        "source": "telegram",
        "user_id": "user123",
        "message": "Hello",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    result = await runtime.process_event(event)
    assert result["status"] == "completed"
    mock_orchestrator.handle.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limiting_enforced(mock_orchestrator):
    """Test rate limiting works."""
    from synapse.connectors.runtime import ConnectorRuntime, RateLimiter
    
    rate_limiter = RateLimiter(max_requests=2, window_seconds=60)
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator, rate_limiter=rate_limiter)
    
    event = {"source": "telegram", "user_id": "user123", "message": "test"}
    
    # First two should succeed
    await runtime.process_event(event)
    await runtime.process_event(event)
    
    # Third should be rate limited
    with pytest.raises(Exception) as exc_info:
        await runtime.process_event(event)
    assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_capability_enforcement_in_connector(mock_orchestrator, mock_capability_manager):
    """Test capability enforcement works in connector."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(
        orchestrator=mock_orchestrator,
        capability_manager=mock_capability_manager
    )
    
    event = {
        "source": "telegram",
        "user_id": "user123",
        "message": "delete file",
        "required_capabilities": ["fs:delete"]
    }
    
    await runtime.process_event(event)
    mock_capability_manager.check.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_human_approval_pipeline(mock_orchestrator):
    """Test human approval pipeline for dangerous actions."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator)
    runtime.set_approval_required(lambda event: event.get("risk_level", 0) >= 3)
    
    event = {
        "source": "telegram",
        "user_id": "user123",
        "message": "delete all files",
        "risk_level": 4
    }
    
    # Should request approval
    result = await runtime.process_event(event)
    assert result["status"] == "pending_approval"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_message_normalization(mock_orchestrator):
    """Test message normalization across different sources."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator)
    
    telegram_event = {"source": "telegram", "text": "Hello", "from": {"id": 123}}
    discord_event = {"source": "discord", "content": "Hello", "author": {"id": 456}}
    
    normalized_telegram = runtime.normalize_event(telegram_event)
    normalized_discord = runtime.normalize_event(discord_event)
    
    # Access as dataclass attributes
    assert normalized_telegram.message == "Hello"
    assert normalized_discord.message == "Hello"
    assert normalized_telegram.user_id == "123"
    assert normalized_discord.user_id == "456"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deterministic_event_ordering(mock_orchestrator):
    """Test deterministic event ordering."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator)
    
    events = [
        {"source": "telegram", "message": "third", "timestamp": "2024-01-01T12:00:03"},
        {"source": "telegram", "message": "first", "timestamp": "2024-01-01T12:00:01"},
        {"source": "telegram", "message": "second", "timestamp": "2024-01-01T12:00:02"},
    ]
    
    ordered = runtime.order_events(events)
    assert ordered[0]["message"] == "first"
    assert ordered[1]["message"] == "second"
    assert ordered[2]["message"] == "third"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connector_no_direct_core_access(mock_orchestrator):
    """Test connector has no direct access to core."""
    from synapse.connectors.runtime import ConnectorRuntime
    
    runtime = ConnectorRuntime(orchestrator=mock_orchestrator)
    
    # Connector should only have orchestrator interface
    assert not hasattr(runtime, 'core')
    assert not hasattr(runtime, 'memory_store')
    assert not hasattr(runtime, 'skill_registry')
