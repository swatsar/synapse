"""Tests for distributed node runtime."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestDistributedNodeRuntime:
    """Test distributed node runtime."""
    
    @pytest.fixture
    def node_runtime(self):
        """Create a node runtime for testing."""
        from synapse.distributed.node_runtime import NodeRuntime
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("node:execute")
        caps.grant_capability("node:status")
        
        # Create mock agents
        agent = MagicMock()
        agent.handle_event = AsyncMock()
        agent.run = AsyncMock()
        
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
        # Event should be in the queue
        assert node_runtime._event_queue.qsize() == 1
