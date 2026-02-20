PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import os
import pytest
from synapse.memory.store import MemoryStore

# Sync fixture that creates a temporary SQLite DB for each test
@pytest.fixture
def mem_store(tmp_path):
    db_path = tmp_path / "test_memory.db"
    # MemoryStore lazily creates the DB on first use, no async init needed here
    return MemoryStore(str(db_path))

@pytest.mark.asyncio
async def test_short_term(mem_store):
    await mem_store.add_short_term("foo", {"val": 1})
    values = await mem_store.get_short_term("foo")
    assert values == [{"val": 1}]

@pytest.mark.asyncio
async def test_long_term_and_search(mem_store):
    await mem_store.add_long_term("bar_key", "bar_value")
    await mem_store.add_long_term("baz_key", "baz_value")
    results = await mem_store.search("bar")
    assert any(r["source"] == "long_term" and r["key"] == "bar_key" for r in results)

@pytest.mark.asyncio
async def test_episodic(mem_store):
    await mem_store.add_episode("ep1", {"step": "start"})
    data = await mem_store.get_episode("ep1")
    assert data == {"step": "start"}
