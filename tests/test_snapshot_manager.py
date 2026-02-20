"""Tests for snapshot manager."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestSnapshotManager:
    """Test snapshot manager."""

    @pytest.fixture
    def snapshot_manager(self):
        """Create a snapshot manager for testing."""
        from synapse.reliability.snapshot_manager import SnapshotManager
        from synapse.security.capability_manager import CapabilityManager

        caps = CapabilityManager()
        caps.grant_capability("snapshot:create")
        caps.grant_capability("snapshot:restore")

        return SnapshotManager(caps=caps)

    def test_snapshot_manager_creation(self, snapshot_manager):
        """Test snapshot manager creation."""
        assert snapshot_manager is not None

    def test_protocol_version(self, snapshot_manager):
        """Test protocol version."""
        assert snapshot_manager.protocol_version == "1.0"

    @pytest.mark.asyncio
    async def test_create_snapshot(self, snapshot_manager):
        """Test creating a snapshot."""
        state = {"test": "data"}
        path = await snapshot_manager.create_snapshot(state)
        assert path is not None

    @pytest.mark.asyncio
    async def test_restore_snapshot(self, snapshot_manager):
        """Test restoring a snapshot."""
        state = {"test": "data"}
        path = await snapshot_manager.create_snapshot(state)
        restored = await snapshot_manager.restore_snapshot(path)
        assert restored == state
