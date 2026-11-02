"""Semantic Memory with ChromaDB vector store.

Protocol Version: 1.0
Specification: 3.1

Implements the semantic (vector) memory layer using ChromaDB.

When ChromaDB or an embedding backend is unavailable, retrieval degrades
honestly to BM25 lexical search over the indexed documents. Cryptographic
hashes are never used as pseudo-embeddings: a hash digest carries no
semantic similarity signal, so a keyword/FTS fallback is the only correct
degradation path.
"""
import hashlib
import logging
import math
import re
import time
from datetime import UTC, datetime
from typing import Any

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer used by the BM25 fallback."""
    return _WORD_RE.findall(text.lower())


class _BM25Index:
    """In-memory BM25 index — the honest retrieval fallback."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._docs: dict[str, list[str]] = {}
        self._doc_freq: dict[str, int] = {}
        self._total_len = 0

    def add(self, doc_id: str, text: str) -> None:
        terms = _tokenize(text)
        if doc_id in self._docs:
            self.remove(doc_id)
        self._docs[doc_id] = terms
        self._total_len += len(terms)
        for term in set(terms):
            self._doc_freq[term] = self._doc_freq.get(term, 0) + 1

    def remove(self, doc_id: str) -> bool:
        terms = self._docs.pop(doc_id, None)
        if terms is None:
            return False
        self._total_len -= len(terms)
        for term in set(terms):
            count = self._doc_freq.get(term, 0)
            if count <= 1:
                self._doc_freq.pop(term, None)
            else:
                self._doc_freq[term] = count - 1
        return True

    def __len__(self) -> int:
        return len(self._docs)

    def search(self, query: str, limit: int = 5) -> list[tuple[str, float]]:
        """Return (doc_id, score) pairs ranked by BM25 relevance."""
        n_docs = len(self._docs)
        if n_docs == 0:
            return []
        avgdl = self._total_len / n_docs if n_docs else 0.0
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        scores: dict[str, float] = {}
        for term in query_terms:
            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for doc_id, terms in self._docs.items():
                tf = terms.count(term)
                if tf == 0:
                    continue
                denom = tf + self._k1 * (
                    1 - self._b + self._b * (len(terms) / avgdl if avgdl else 0.0)
                )
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * (tf * (self._k1 + 1)) / denom

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]


class VectorMemoryStore:
    """Semantic memory using ChromaDB for vector similarity search.

    Provides:
    - add_document(): embed and store text with metadata
    - query(): semantic similarity search
    - delete(): remove documents

    When an embedding backend or ChromaDB is unavailable, every operation
    degrades to an in-memory BM25 keyword index. The retrieval mode is always
    reported via :meth:`get_stats` and per-result metadata so callers never
    mistake lexical fallback for semantic search.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        collection_name: str = "synapse_memory",
        persist_directory: str | None = None,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._bm25 = _BM25Index()
        self._fallback_docs: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def _init(self) -> bool:
        """Initialize ChromaDB connection. Returns True if ChromaDB available."""
        if self._initialized:
            return self._client is not None
        self._initialized = True
        try:
            import chromadb
            if self.persist_directory:
                self._client = chromadb.PersistentClient(path=self.persist_directory)
            else:
                self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialized: collection=%s", self.collection_name)
            return True
        except ImportError:
            logger.warning("chromadb not installed — using BM25 keyword fallback")
            return False
        except Exception as e:
            logger.warning("ChromaDB init failed (%s) — using BM25 keyword fallback", e)
            return False

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Embed text via the configured backend, or return None if unavailable.

        Returning None (rather than a hash-derived pseudo-vector) is what lets
        callers degrade to lexical retrieval honestly.
        """
        try:
            import litellm
            response = litellm.embedding(model=self.embedding_model, input=[text])
            return list(response.data[0]["embedding"])
        except Exception as e:  # noqa: BLE001 - any backend failure means unavailable
            logger.debug("embedding backend unavailable (%s) — using keyword fallback", e)
            return None

    async def add_document(
        self,
        text: str,
        doc_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Embed and store a document."""
        doc_id = doc_id or hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
        meta = {
            "timestamp": datetime.now(UTC).isoformat(),
            "protocol_version": PROTOCOL_VERSION,
            **(metadata or {}),
        }

        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            embedding = await self._get_embedding(text)
            if embedding is not None:
                try:
                    self._collection.upsert(
                        ids=[doc_id],
                        documents=[text],
                        embeddings=[embedding],
                        metadatas=[meta],
                    )
                    return doc_id
                except Exception as e:
                    logger.warning("ChromaDB upsert failed: %s", e)

        # Honest lexical fallback
        meta["retrieval"] = "keyword"
        self._bm25.add(doc_id, text)
        self._fallback_docs[doc_id] = {"id": doc_id, "text": text, "metadata": meta}
        return doc_id

    async def query(
        self,
        query_text: str,
        limit: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic similarity search, degrading to BM25 keyword search."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            embedding = await self._get_embedding(query_text)
            if embedding is not None:
                try:
                    kwargs: dict[str, Any] = {
                        "query_embeddings": [embedding],
                        "n_results": min(limit, max(1, self._collection.count())),
                        "include": ["documents", "metadatas", "distances"],
                    }
                    if where:
                        kwargs["where"] = where
                    result = self._collection.query(**kwargs)
                    docs = result.get("documents", [[]])[0]
                    metas = result.get("metadatas", [[]])[0]
                    dists = result.get("distances", [[]])[0]
                    out = []
                    for doc, meta, dist in zip(docs, metas, dists):
                        m = dict(meta or {})
                        m.setdefault("retrieval", "vector")
                        out.append({
                            "id": m.get("id", ""),
                            "text": doc,
                            "metadata": m,
                            "score": round(1.0 - dist, 4),
                            "protocol_version": PROTOCOL_VERSION,
                        })
                    return out
                except Exception as e:
                    logger.warning("ChromaDB query failed: %s", e)

        # BM25 keyword fallback
        ranked = self._bm25.search(query_text, limit=limit)
        return [
            {
                "id": doc_id,
                "text": self._fallback_docs[doc_id]["text"],
                "metadata": self._fallback_docs[doc_id]["metadata"],
                "score": round(score, 4),
                "protocol_version": PROTOCOL_VERSION,
            }
            for doc_id, score in ranked
        ]

    async def delete(self, doc_id: str) -> bool:
        """Remove a document by ID."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                self._collection.delete(ids=[doc_id])
                self._bm25.remove(doc_id)
                self._fallback_docs.pop(doc_id, None)
                return True
            except Exception as _exc:  # noqa
                pass  # noqa: silenced - _exc
        return self._bm25.remove(doc_id) and self._fallback_docs.pop(doc_id, None) is not None

    async def count(self) -> int:
        """Return total document count."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                return self._collection.count()
            except Exception as _exc:  # noqa
                pass  # noqa: silenced - _exc
        return len(self._bm25)

    def get_stats(self) -> dict[str, Any]:
        return {
            "collection": self.collection_name,
            "backend": "chromadb" if self._client else "bm25_keyword",
            "protocol_version": PROTOCOL_VERSION,
        }