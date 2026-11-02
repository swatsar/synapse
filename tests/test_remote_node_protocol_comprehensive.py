"""Comprehensive tests for remote node protocol."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestRemoteNodeProtocolComprehensive:
    """Test remote node protocol comprehensively."""
    
    @pytest.fixture
    def protocol(self):
        """Create a remote node protocol for testing."""
        from synapse.network.remote_node_protocol import RemoteNodeProtocol
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("node:trust")
        caps.grant_capability("handshake")
        
        return RemoteNodeProtocol(caps=caps, node_id="test_node")
    
    def test_protocol_creation(self, protocol):
        """Test protocol creation."""
        assert protocol is not None
    
    def test_protocol_version(self, protocol):
        """Test protocol version."""
        assert protocol.protocol_version == "1.0"
    
    def test_node_id(self, protocol):
        """Test node ID."""
        assert protocol.node_id == "test_node"
    
    @pytest.mark.asyncio
    async def test_handle_handshake(self, protocol):
        """Test handling a handshake request."""
        from synapse.network.remote_node_protocol import HandshakeRequest
        
        request = HandshakeRequest(
            node_id="remote_node",
            capabilities=["test:capability"]
        )
        
        response = await protocol.handle_handshake(request)
        
        assert response is not None
        assert response.accepted == True
        assert response.node_id == "test_node"
    
    @pytest.mark.asyncio
    async def test_prepare_message(self, protocol):
        """Test preparing a message."""
        envelope = await protocol.prepare_message(payload={"test": "data"})
        
        assert envelope is not None
        assert "node_id" in envelope
        assert envelope["node_id"] == "test_node"
        assert "protocol_version" in envelope
        assert envelope["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_validate_incoming(self, protocol):
        """Test validating an incoming message."""
        # First negotiate capabilities
        from synapse.network.remote_node_protocol import HandshakeRequest
        request = HandshakeRequest(
            node_id="remote_node",
            capabilities=["test:capability"]
        )
        await protocol.handle_handshake(request)
        
        # Now validate a message with matching capabilities
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "timestamp": 1234567890.0,
            "node_id": "remote_node",
            "capabilities": ["test:capability"],
            "payload": {"test": "data"}
        }
        
        message = await protocol.validate_incoming(envelope)
        assert message is not None
    
    @pytest.mark.asyncio
    async def test_validate_incoming_capability_mismatch(self, protocol):
        """Test validating an incoming message with capability mismatch."""
        # First negotiate capabilities
        from synapse.network.remote_node_protocol import HandshakeRequest
        request = HandshakeRequest(
            node_id="remote_node",
            capabilities=["test:capability"]
        )
        await protocol.handle_handshake(request)
        
        # Now validate a message with non-matching capabilities
        envelope = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "timestamp": 1234567890.0,
            "node_id": "remote_node",
            "capabilities": ["other:capability"],
            "payload": {"test": "data"}
        }
        
        with pytest.raises(PermissionError, match="Capability mismatch"):
            await protocol.validate_incoming(envelope)
