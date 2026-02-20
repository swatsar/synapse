"""Comprehensive tests for distributed node runtime."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDistributedNodeRuntimeComprehensive:
    """Test distributed node runtime comprehensively."""
    
    @pytest.fixture
    def node_runtime(self):
        """Create a node runtime for testing."""
        from synapse.distributed.node_runtime import NodeRuntime
        from synapse.security.capability_manager import CapabilityManager
        
        # Create mock agents
        agent = AsyncMock()
        agent.run = AsyncMock()
        agent.handle_event = AsyncMock()
        
        caps = CapabilityManager()
        caps.grant_capability("node:execute")
        
        return NodeRuntime(agents=[agent], caps=caps)
    
    def test_node_runtime_creation(self, node_runtime):
        """Test node runtime creation."""
        assert node_runtime is not None
    
    def test_protocol_version(self, node_runtime):
        """Test protocol version."""
        assert node_runtime.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_post_event(self, node_runtime):
        """Test posting an event."""
        event = {"test": "event"}
        await node_runtime.post_event(event)
        
        # Check event was posted
        assert node_runtime._event_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_dispatch(self, node_runtime):
        """Test dispatching an event."""
        event = {"test": "event"}
        
        await node_runtime._dispatch(event)
        
        # Check that agents received the event
        for agent in node_runtime._agents:
            agent.handle_event.assert_called_once_with(event)
