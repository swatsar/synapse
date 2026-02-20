"""Full tests for distributed node runtime."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDistributedNodeRuntimeFull:
    """Test distributed node runtime comprehensively."""
    
    @pytest.fixture
    def node_runtime(self):
        """Create a distributed node runtime for testing."""
        from synapse.distributed.node_runtime import NodeRuntime
        from synapse.security.capability_manager import CapabilityManager
        
        # Create mock agents
        agent = MagicMock()
        agent.handle_event = AsyncMock()
        agent.run = AsyncMock()
        
        caps = CapabilityManager()
        caps.grant_capability("test:capability")
        
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
        event = {"type": "test", "data": "test_data"}
        
        await node_runtime.post_event(event)
        
        assert node_runtime._event_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_dispatch(self, node_runtime):
        """Test dispatching an event."""
        event = {"type": "test", "data": "test_data"}
        
        await node_runtime._dispatch(event)
        
        # Check that the agent's handle_event was called
        for agent in node_runtime._agents:
            agent.handle_event.assert_called_once_with(event)
