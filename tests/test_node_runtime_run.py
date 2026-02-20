"""Tests for NodeRuntime run method."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestNodeRuntimeRun:
    """Test NodeRuntime run method."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock RuntimeAgent."""
        agent = MagicMock()
        agent.run = AsyncMock()
        agent.handle_event = AsyncMock()
        return agent
    
    @pytest.fixture
    def capability_manager(self):
        """Create a CapabilityManager for testing."""
        from synapse.security.capability_manager import CapabilityManager
        caps = CapabilityManager()
        caps.grant_capability("test:event")
        return caps
    
    @pytest.mark.asyncio
    async def test_run_dispatches_events(self, mock_agent, capability_manager):
        """Test that run dispatches events to agents."""
        from synapse.distributed.node_runtime import NodeRuntime
        
        runtime = NodeRuntime(agents=[mock_agent], caps=capability_manager)
        
        # Create a task to post an event and then stop
        async def post_and_stop():
            await asyncio.sleep(0.1)
            await runtime.post_event({"type": "test", "required_capabilities": ["test:event"]})
            await asyncio.sleep(0.1)
            # Cancel the run task
            for task in asyncio.all_tasks():
                if task.get_name() == "node_runtime_run":
                    task.cancel()
        
        # Run both tasks
        run_task = asyncio.create_task(runtime.run(), name="node_runtime_run")
        post_task = asyncio.create_task(post_and_stop())
        
        try:
            await asyncio.wait_for(run_task, timeout=1.0)
        except asyncio.CancelledError:
            pass
        
        await post_task
        
        # Verify agent received the event
        mock_agent.handle_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_run_starts_agents(self, mock_agent, capability_manager):
        """Test that run starts all agents."""
        from synapse.distributed.node_runtime import NodeRuntime
        
        runtime = NodeRuntime(agents=[mock_agent], caps=capability_manager)
        
        # Create a task to cancel after a short delay
        async def cancel_after_delay():
            await asyncio.sleep(0.1)
            for task in asyncio.all_tasks():
                if task.get_name() == "node_runtime_run":
                    task.cancel()
        
        run_task = asyncio.create_task(runtime.run(), name="node_runtime_run")
        cancel_task = asyncio.create_task(cancel_after_delay())
        
        try:
            await asyncio.wait_for(run_task, timeout=1.0)
        except asyncio.CancelledError:
            pass
        
        await cancel_task
        
        # Verify agent run was called
        mock_agent.run.assert_called()
    
    @pytest.mark.asyncio
    async def test_post_event(self, mock_agent, capability_manager):
        """Test posting events to the queue."""
        from synapse.distributed.node_runtime import NodeRuntime
        
        runtime = NodeRuntime(agents=[mock_agent], caps=capability_manager)
        
        # Post an event
        await runtime.post_event({"type": "test"})
        
        # Verify event is in queue
        assert not runtime._event_queue.empty()
