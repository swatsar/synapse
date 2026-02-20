"""Tests for RemoteNodeProtocol with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRemoteNodeProtocolFull:
    """Test RemoteNodeProtocol with full coverage."""
    
    @pytest.fixture
    def protocol(self):
        """Create a RemoteNodeProtocol."""
        from synapse.network.remote_node_protocol import RemoteNodeProtocol
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("handshake")
        caps.grant_capability("node:trust")
        
        return RemoteNodeProtocol(
            caps=caps,
            node_id="test_node"
        )
    
    def test_node_identity_creation(self):
        """Test NodeIdentity creation."""
        from synapse.network.remote_node_protocol import NodeIdentity
        
        identity = NodeIdentity(
            node_id="test_node",
            protocol_version="1.0"
        )
        
        assert identity.node_id == "test_node"
        assert identity.protocol_version == "1.0"
    
    def test_node_identity_version_mismatch(self):
        """Test NodeIdentity with wrong protocol version."""
        from synapse.network.remote_node_protocol import NodeIdentity
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            NodeIdentity(
                node_id="test_node",
                protocol_version="2.0"
            )
    
    def test_remote_message_creation(self):
        """Test RemoteMessage creation."""
        from synapse.network.remote_node_protocol import RemoteMessage
        
        message = RemoteMessage(
            payload={"test": "data"}
        )
        
        assert message.protocol_version == "1.0"
        assert message.payload == {"test": "data"}
    
    def test_remote_message_normalise_timestamp(self):
        """Test RemoteMessage normalise_timestamp."""
        from synapse.network.remote_node_protocol import RemoteMessage
        
        message = RemoteMessage(
            timestamp=1700000000.0,
            payload={}
        )
        
        message.normalise_timestamp()
        assert isinstance(message.timestamp, float)
    
    def test_handshake_request_creation(self):
        """Test HandshakeRequest creation."""
        from synapse.network.remote_node_protocol import HandshakeRequest
        
        request = HandshakeRequest(
            node_id="test_node",
            capabilities=["test:cap"]
        )
        
        assert request.node_id == "test_node"
        assert request.protocol_version == "1.0"
        assert request.capabilities == ["test:cap"]
    
    def test_handshake_response_creation(self):
        """Test HandshakeResponse creation."""
        from synapse.network.remote_node_protocol import HandshakeResponse
        
        response = HandshakeResponse(
            node_id="server_node",
            accepted=True,
            negotiated_capabilities=["test:cap"]
        )
        
        assert response.node_id == "server_node"
        assert response.accepted == True
        assert response.negotiated_capabilities == ["test:cap"]
    
    @pytest.mark.asyncio
    async def test_protocol_handshake(self, protocol):
        """Test protocol handshake."""
        from synapse.network.remote_node_protocol import HandshakeRequest
        
        request = HandshakeRequest(
            node_id="client_node",
            capabilities=["test:cap"]
        )
        
        response = await protocol.handle_handshake(request)
        assert response is not None
        assert response.accepted == True
    
    @pytest.mark.asyncio
    async def test_protocol_create_message(self, protocol):
        """Test protocol create_message."""
        message = await protocol.prepare_message(
            payload={"test": "data"}
        )
        
        assert message is not None
        assert message["payload"] == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_protocol_validate_message(self, protocol):
        """Test protocol validate_message."""
        from synapse.network.remote_node_protocol import RemoteMessage
        
        # First negotiate capabilities
        from synapse.network.remote_node_protocol import HandshakeRequest
        request = HandshakeRequest(
            node_id="client_node",
            capabilities=["test:cap"]
        )
        await protocol.handle_handshake(request)
        
        envelope_dict = {
            "protocol_version": "1.0",
            "trace_id": "test_trace",
            "timestamp": 1700000000.0,
            "node_id": "test_node",
            "capabilities": ["test:cap"],
            "payload": {"test": "data"}
        }
        
        result = await protocol.validate_incoming(envelope_dict)
        assert result is not None
