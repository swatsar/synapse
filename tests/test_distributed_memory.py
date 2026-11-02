"""Tests for distributed memory store."""
import pytest
from unittest.mock import MagicMock


class TestDistributedMemory:
    """Test distributed memory store."""

    @pytest.fixture
    def capability_manager(self):
        """Create a capability manager for testing."""
        from synapse.security.capability_manager import CapabilityManager
        cm = CapabilityManager()
        cm.grant_capability("memory:write")
        cm.grant_capability("memory:read")
        cm.grant_capability("memory:replicate")
        return cm

    def test_distributed_memory_creation(self, capability_manager):
        """Test distributed memory creation."""
        from synapse.memory.distributed.store import DistributedMemoryStore
        store = DistributedMemoryStore(capability_manager)
        assert store is not None

    @pytest.mark.asyncio
    async def test_distributed_memory_add(self, capability_manager):
        """Test distributed memory add."""
        from synapse.memory.distributed.store import DistributedMemoryStore
        store = DistributedMemoryStore(capability_manager)
        await store.add_long_term("test", {"data": "value"})

    @pytest.mark.asyncio
    async def test_distributed_memory_replicate(self, capability_manager):
        """Test distributed memory replicate."""
        from synapse.memory.distributed.store import DistributedMemoryStore
        store = DistributedMemoryStore(capability_manager)
        await store.replicate()
