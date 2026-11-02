"""Tests for cluster manager."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestClusterManager:
    """Test cluster manager."""

    @pytest.fixture
    def cluster_manager(self):
        """Create a cluster manager for testing."""
        from synapse.runtime.cluster.manager import ClusterManager
        from synapse.distributed.node_runtime import NodeRuntime
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("cluster:manage")
        caps.grant_capability("cluster:status")
        caps.grant_capability("cluster:snapshot")
        caps.grant_capability("cluster:rollback")
        caps.grant_capability("rollback")  # Required for rollback operations
        # SnapshotManager requires these capabilities
        caps.grant_capability("snapshot:create")
        caps.grant_capability("snapshot:restore")

        # Create mock node runtime
        agent = MagicMock()
        agent.handle_event = AsyncMock()
        agent.run = AsyncMock()
        node = NodeRuntime(agents=[agent], caps=caps)

        return ClusterManager(caps=caps, nodes=[node])

    def test_cluster_manager_creation(self, cluster_manager):
        """Test cluster manager creation."""
        assert cluster_manager is not None

    def test_protocol_version(self, cluster_manager):
        """Test protocol version."""
        assert cluster_manager.protocol_version == "1.0"

    @pytest.mark.asyncio
    async def test_create_cluster_snapshot(self, cluster_manager):
        """Test creating cluster snapshot."""
        paths = await cluster_manager.create_cluster_snapshot()
        assert isinstance(paths, list)

    @pytest.mark.asyncio
    async def test_rollback_cluster(self, cluster_manager):
        """Test cluster rollback."""
        # First create a snapshot
        paths = await cluster_manager.create_cluster_snapshot()

        # Then rollback
        states = await cluster_manager.rollback_cluster(paths)
        assert isinstance(states, list)
