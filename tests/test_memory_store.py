"""Tests for memory store."""
import pytest
import tempfile
import os


class TestMemoryStore:
    """Test memory store."""

    @pytest.fixture
    def memory_store(self):
        """Create a memory store for testing."""
        from synapse.memory.store import MemoryStore
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = MemoryStore(db_path=db_path)
            yield store

    @pytest.mark.asyncio
    async def test_memory_store_creation(self, memory_store):
        """Test memory store creation."""
        assert memory_store is not None

    @pytest.mark.asyncio
    async def test_memory_store_add_short_term(self, memory_store):
        """Test adding short-term memory."""
        await memory_store.add_short_term("test_key", {"data": "value"})

    @pytest.mark.asyncio
    async def test_memory_store_get_short_term(self, memory_store):
        """Test getting short-term memory."""
        await memory_store.add_short_term("test_key", {"data": "value"})
        result = await memory_store.get_short_term("test_key")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_memory_store_add_long_term(self, memory_store):
        """Test adding long-term memory."""
        await memory_store.add_long_term("test_category", {"data": "value"})

    @pytest.mark.asyncio
    async def test_memory_store_query_long_term(self, memory_store):
        """Test querying long-term memory."""
        await memory_store.add_long_term("test_category", {"data": "value"})
        results = await memory_store.query_long_term("test")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_memory_store_add_episodic(self, memory_store):
        """Test adding episode."""
        await memory_store.add_episodic("episode_1", {"event": "test"})

    @pytest.mark.asyncio
    async def test_memory_store_get_episode(self, memory_store):
        """Test getting episode."""
        await memory_store.add_episodic("episode_1", {"event": "test"})
        result = await memory_store.get_episode("episode_1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_memory_store_search(self, memory_store):
        """Test searching memory."""
        await memory_store.add_long_term("test_category", {"data": "value"})
        results = await memory_store.search("test")
        assert isinstance(results, list)
