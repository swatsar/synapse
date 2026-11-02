"""Tests for replication manager."""
import pytest
from unittest.mock import MagicMock


class TestReplicationManager:
    """Test replication manager."""

    @pytest.fixture
    def replication_manager(self):
        """Create a replication manager for testing."""
        from synapse.distributed.replication.manager import ReplicationManager
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("replication:send")
        caps.grant_capability("replication:receive")

        return ReplicationManager(caps=caps)

    def test_replication_manager_creation(self, replication_manager):
        """Test replication manager creation."""
        assert replication_manager is not None

    @pytest.mark.asyncio
    async def test_replicate(self, replication_manager):
        """Test replicating data."""
        await replication_manager.replicate("node1", {"test": "data"})
        replications = await replication_manager.fetch_replications("node1")
        assert len(replications) == 1
        assert replications[0] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_fetch_replications(self, replication_manager):
        """Test fetching replications."""
        await replication_manager.replicate("node1", {"test": "data1"})
        await replication_manager.replicate("node1", {"test": "data2"})
        replications = await replication_manager.fetch_replications("node1")
        assert len(replications) == 2
