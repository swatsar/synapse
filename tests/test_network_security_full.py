"""Comprehensive tests for network security."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestNetworkSecurityFull:
    """Test network security comprehensively."""
    
    @pytest.fixture
    def security(self):
        """Create network security for testing."""
        from synapse.network.security import MessageSecurity
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("node:trust")
        caps.grant_capability("test:capability")
        
        return MessageSecurity(caps=caps)
    
    def test_security_creation(self, security):
        """Test security creation."""
        assert security is not None
    
    def test_protocol_version(self, security):
        """Test protocol version."""
        assert security.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_authorize_message(self, security):
        """Test authorizing a message."""
        envelope = {
            "protocol_version": "1.0",
            "capabilities": ["test:capability"],
            "source_node": "node1",
            "target_node": "node2",
            "message_type": "test",
            "payload": {"test": "data"}
        }
        
        # Should not raise
        await security.authorize_message(envelope)
    
    @pytest.mark.asyncio
    async def test_authorize_message_protocol_mismatch(self, security):
        """Test authorizing a message with protocol mismatch."""
        envelope = {
            "protocol_version": "2.0",
            "capabilities": ["test:capability"],
            "source_node": "node1",
            "target_node": "node2",
            "message_type": "test",
            "payload": {"test": "data"}
        }
        
        with pytest.raises(ValueError, match="protocol_version mismatch"):
            await security.authorize_message(envelope)
    
    @pytest.mark.asyncio
    async def test_authorize_message_replay(self, security):
        """Test authorizing a message with replay detection."""
        envelope = {
            "protocol_version": "1.0",
            "capabilities": ["test:capability"],
            "source_node": "node1",
            "target_node": "node2",
            "message_type": "test",
            "payload": {"test": "data"}
        }
        
        # First call should succeed
        await security.authorize_message(envelope)
        
        # Second call with same envelope should fail (replay)
        with pytest.raises(PermissionError, match="Replay attack detected"):
            await security.authorize_message(envelope)
