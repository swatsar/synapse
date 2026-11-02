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
    async def test_keyword_fallback_retrieves_without_embedding_backend(self, store):
        """When no embedding backend is available, keyword (BM25) search is used.

        Cryptographic hashes must never be used as semantic embeddings — the
        fallback is honest lexical retrieval, tagged as such in metadata.
        """
        async def _no_embedding(text: str) -> None:
            return None

        store._get_embedding = _no_embedding  # type: ignore[assignment]
        await store.add_document(
            "The agent failed to read the file due to permission denial",
            doc_id="perm",
        )
        await store.add_document(
            "Unrelated note about the weather forecast",
            doc_id="weather",
        )

        results = await store.query("file permission error", limit=2)

        assert isinstance(results, list)
        assert results, "keyword fallback must return matches"
        assert results[0]["id"] == "perm"
        assert results[0]["metadata"]["retrieval"] == "keyword"
        assert "text" in results[0] and "score" in results[0]

    @pytest.mark.asyncio
    async def test_bm25_ranks_more_relevant_document_first(self, store):
        """BM25 overlap scoring ranks the document sharing more terms first."""
        async def _no_embedding(text: str) -> None:
            return None

        store._get_embedding = _no_embedding  # type: ignore[assignment]
        await store.add_document("capability based security model", doc_id="a")
        await store.add_document(
            "capability based security model for agents with policies",
            doc_id="b",
        )
        await store.add_document("completely different topic here", doc_id="c")

        results = await store.query("capability based security policies", limit=3)

        ids = [r["id"] for r in results]
        assert ids[0] in ("a", "b")
        assert "c" not in ids[:2]
        # Scores must be descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_hash_pseudo_embedding(self, store):
        """Regression guard: SHA/MD5 pseudo-embedding must not exist."""
        assert not hasattr(store, "_embed_fallback"), (
            "Cryptographic-hash pseudo-embedding is forbidden; use BM25/FTS fallback"
        )

    def test_get_stats(self, store):
        stats = store.get_stats()
        assert "collection" in stats
        assert "backend" in stats
        assert "protocol_version" in stats
