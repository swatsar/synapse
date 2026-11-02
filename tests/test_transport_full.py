"""Tests for Transport with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestTransportFull:
    """Test Transport with full coverage."""
    
    @pytest.fixture
    def transport(self):
        """Create a Transport."""
        from synapse.network.transport import Transport
        from synapse.security.capability_manager import CapabilityManager
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.core.models import ResourceLimits
        
        caps = CapabilityManager()
        caps.grant_capability("test:cap")
        
        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        guard = ExecutionGuard(limits=limits)
        
        return Transport(caps=caps, guard=guard)
    
    @pytest.mark.asyncio
    async def test_transport_send_message(self, transport):
        """Test transport send_message."""
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "payload": {"test": "data"},
            "capabilities": ["test:cap"]
        }
        
        await transport.send_message(envelope)
        
        assert len(transport._outbox) == 1
    
    @pytest.mark.asyncio
    async def test_transport_receive_message(self, transport):
        """Test transport receive_message."""
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "payload": {"test": "data"}
        }
        
        transport.inject_incoming(envelope)
        
        result = await transport.receive_message(timeout=1.0)
        
        assert result is not None
        assert result["trace_id"] == "test_trace"
    
    @pytest.mark.asyncio
    async def test_transport_receive_timeout(self, transport):
        """Test transport receive_message timeout."""
        import asyncio
        
        with pytest.raises(asyncio.TimeoutError):
            await transport.receive_message(timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_transport_send_with_caps(self, transport):
        """Test transport send_message with required_caps."""
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "payload": {"test": "data"}
        }
        
        await transport.send_message(envelope, required_caps=["test:cap"])
        
        assert len(transport._outbox) == 1
    
    def test_transport_inject_incoming(self, transport):
        """Test transport inject_incoming."""
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "payload": {"test": "data"}
        }
        
        transport.inject_incoming(envelope)
        
        assert len(transport._inbox) == 1
