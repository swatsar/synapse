"""Tests for coordination service."""
import pytest
from unittest.mock import MagicMock


class TestClusterCoordinationService:
    """Test cluster coordination service."""

    @pytest.fixture
    def coordination_service(self):
        """Create a coordination service for testing."""
        from synapse.distributed.coordination.service import ClusterCoordinationService
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("coordination:register")
        caps.grant_capability("coordination:broadcast")
        caps.grant_capability("coordination:read")

        return ClusterCoordinationService(caps=caps)

    def test_coordination_service_creation(self, coordination_service):
        """Test coordination service creation."""
        assert coordination_service is not None

    @pytest.mark.asyncio
    async def test_register_node(self, coordination_service):
        """Test registering a node."""
        await coordination_service.register_node("node1")
        assert "node1" in coordination_service._node_registry

    @pytest.mark.asyncio
    async def test_broadcast(self, coordination_service):
        """Test broadcasting an event."""
        await coordination_service.register_node("node1")
        await coordination_service.broadcast("node1", {"test": "data"})
        log = await coordination_service.fetch_log()
        assert len(log) == 1
        assert log[0]["node_id"] == "node1"

    @pytest.mark.asyncio
    async def test_fetch_log(self, coordination_service):
        """Test fetching the event log."""
        await coordination_service.register_node("node1")
        await coordination_service.broadcast("node1", {"test": "data"})
        log = await coordination_service.fetch_log()
        assert len(log) == 1
