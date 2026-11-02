import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.security.capability_manager import CapabilityManager
from synapse.network.remote_node_protocol import (
    NodeIdentity,
    RemoteMessage,
    HandshakeRequest,
    HandshakeResponse,
    RemoteNodeProtocol,
)

@pytest.fixture
def caps():
    caps = CapabilityManager()
    # Grant required capabilities for tests
    caps.grant_capability("handshake")
    caps.grant_capability("node:trust")
    return caps

@pytest.fixture
def protocol(caps):
    # Minimal protocol instance – we will mock the transport later
    return RemoteNodeProtocol(caps=caps, node_id="nodeA")

@pytest.mark.asyncio
async def test_handshake_validation(protocol):
    # Handshake request must contain correct protocol_version
    request = HandshakeRequest(node_id="nodeB", protocol_version="1.0")
    response = await protocol.handle_handshake(request)
    assert isinstance(response, HandshakeResponse)
    assert response.protocol_version == "1.0"
    assert response.accepted is True

@pytest.mark.asyncio
async def test_timestamp_normalisation(protocol):
    # Ensure outgoing messages have a UTC timestamp (float) and are deterministic
    payload = {"action": "ping"}
    envelope = await protocol.prepare_message(payload)
    # Timestamp should be a float and not None
    assert isinstance(envelope["timestamp"], float)
    # Keys must be sorted – JSON dump with sort_keys=True yields deterministic string
    json_str = json.dumps(envelope, sort_keys=True)
    # Ensure protocol_version appears
    assert "protocol_version" in json_str

@pytest.mark.asyncio
async def test_capability_negotiation(protocol, caps):
    # Simulate a remote node that requests a capability we do not have
    request = HandshakeRequest(node_id="nodeB", protocol_version="1.0", capabilities=["foo"])
    # CapabilityManager by default denies unknown caps – we mock it to allow
    caps.check_capability = AsyncMock(return_value=True)
    response = await protocol.handle_handshake(request)
    assert response.accepted is True
    # After handshake, protocol should have negotiated caps
    assert "foo" in protocol.negotiated_capabilities
