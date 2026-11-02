import asyncio
import pytest
from unittest.mock import AsyncMock

from synapse.security.capability_manager import CapabilityManager
from synapse.network.security import MessageSecurity

@pytest.fixture
def caps():
    caps = CapabilityManager()
    caps.grant_capability("node:trust")
    return caps

@pytest.fixture
def security(caps):
    return MessageSecurity(caps=caps)

@pytest.mark.asyncio
async def test_unauthorized_message_rejected(security, caps):
    # Message missing required capability should raise PermissionError
    caps.check_capability = AsyncMock(side_effect=PermissionError("missing"))
    msg = {"protocol_version": "1.0", "node_id": "nodeA", "payload": {}}
    with pytest.raises(PermissionError):
        await security.authorize_message(msg)

@pytest.mark.asyncio
async def test_audit_logging(security, caps, monkeypatch):
    # Ensure audit log is called on successful auth
    logged = []
    def fake_audit(event, **kw):
        logged.append({"event": event, **kw})
    # Patch where the function is used, not where it's defined
    monkeypatch.setattr("synapse.network.security.audit", fake_audit)
    caps.check_capability = AsyncMock(return_value=True)
    msg = {"protocol_version": "1.0", "node_id": "nodeA", "payload": {}}
    await security.authorize_message(msg)
    # Check that audit was called with network_security event
    assert any(entry.get("event") == "network_security" and entry.get("result") == "authorized" for entry in logged)
