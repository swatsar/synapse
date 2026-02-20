"""Unit tests for synapse/network/transport.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from synapse.network.transport import Transport
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.core.models import ResourceLimits

pytestmark = pytest.mark.unit


@pytest.fixture
def limits():
    return ResourceLimits(
        cpu_seconds=60,
        memory_mb=512,
        disk_mb=100,
        network_kb=1024
    )


@pytest.fixture
def caps():
    m = MagicMock(spec=CapabilityManager)
    m.check_capability = AsyncMock(return_value=True)
    return m


@pytest.fixture
def guard(limits):
    return ExecutionGuard(limits=limits)


@pytest.fixture
def transport(caps, guard):
    return Transport(caps=caps, guard=guard)


@pytest.mark.asyncio
async def test_send_message_enforces_capability(transport):
    envelope = {"type": "test", "capabilities": ["net:send"], "protocol_version": "1.0"}
    await transport.send_message(envelope, required_caps=["net:send"])
    transport._caps.check_capability.assert_called()


@pytest.mark.asyncio
async def test_send_message_rejects_missing_capability(transport):
    transport._caps.check_capability = AsyncMock(side_effect=PermissionError("denied"))
    envelope = {"type": "test", "capabilities": ["net:forbidden"], "protocol_version": "1.0"}
    with pytest.raises(PermissionError):
        await transport.send_message(envelope, required_caps=["net:forbidden"])


@pytest.mark.asyncio
async def test_receive_message_timeout(transport):
    with pytest.raises(TimeoutError):
        await transport.receive_message(timeout=0.1)
