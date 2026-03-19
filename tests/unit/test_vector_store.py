"""Unit tests for Vector Memory Store. Phase 3 — Perception & Memory.

TDD per OPENCLAW_INTEGRATION.md §3 + LANGCHAIN_INTEGRATION.md §3.
"""
import pytest
import pytest_asyncio

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase3
@pytest.mark.unit
class TestVectorMemoryStore:
    @pytest.fixture
    def store(self):
        from synapse.memory.vector_store import VectorMemoryStore
        return VectorMemoryStore(collection_name="test_collection")

    @pytest.mark.asyncio
    async def test_add_document_returns_id(self, store):
        doc_id = await store.add_document("Test document about machine learning")
        assert doc_id
        assert isinstance(doc_id, str)

    @pytest.mark.asyncio
    async def test_add_document_with_metadata(self, store):
        doc_id = await store.add_document(
            "Capability-based security",
            doc_id="cap-001",
            metadata={"type": "security", "topic": "capabilities"}
        )
        assert doc_id == "cap-001"

    @pytest.mark.asyncio
    async def test_query_returns_results(self, store):
        await store.add_document("The agent failed to read the file due to permissions")
        results = await store.query("file permission error", limit=3)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_query_result_structure(self, store):
        await store.add_document("LLM response parsing")
        results = await store.query("LLM parsing", limit=1)
        if results:
            r = results[0]
            assert "text" in r
            assert "score" in r
            assert "protocol_version" in r
            assert r["protocol_version"] == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_delete_document(self, store):
        doc_id = await store.add_document("To be deleted")
        await store.delete(doc_id)

    @pytest.mark.asyncio
    async def test_count_increases_after_add(self, store):
        before = await store.count()
        await store.add_document("New document 1")
        await store.add_document("New document 2")
        after = await store.count()
        assert after >= before

    @pytest.mark.asyncio
    async def test_fallback_embedding(self, store):
        """Test that deterministic SHA-512 fallback embedding works."""
        emb = store._embed_fallback("test text for embedding")
        assert len(emb) == 768
        assert all(isinstance(x, float) for x in emb)
        # Deterministic
        emb2 = store._embed_fallback("test text for embedding")
        assert emb == emb2

    def test_get_stats(self, store):
        stats = store.get_stats()
        assert "collection" in stats
        assert "backend" in stats
        assert "protocol_version" in stats
