"""Tests for DistributedMemoryStore with full coverage."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDistributedMemoryStoreFull:
    """Test DistributedMemoryStore with full coverage."""
    
    @pytest.fixture
    def distributed_store(self):
        """Create a DistributedMemoryStore."""
        from synapse.memory.distributed.store import DistributedMemoryStore
        from synapse.security.capability_manager import CapabilityManager
        
        caps = CapabilityManager()
        caps.grant_capability("memory:write")
        caps.grant_capability("memory:read")
        caps.grant_capability("memory:replicate")
        
        return DistributedMemoryStore(caps=caps)
    
    def test_distributed_memory_store_creation(self, distributed_store):
        """Test DistributedMemoryStore creation."""
        assert distributed_store is not None
        assert distributed_store.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_add_long_term(self, distributed_store):
        """Test add_long_term."""
        await distributed_store.add_long_term("test_category", {"test": "data"})
    
    @pytest.mark.asyncio
    async def test_query(self, distributed_store):
        """Test query."""
        # First add some data
        await distributed_store.add_long_term("test_category", {"test": "data"})
        
        # Then query
        results = await distributed_store.query("test", limit=10)
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_replicate(self, distributed_store):
        """Test replicate."""
        await distributed_store.replicate()
