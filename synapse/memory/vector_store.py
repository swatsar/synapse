"""Semantic Memory with ChromaDB vector store.

Protocol Version: 1.0
Specification: 3.1

Implements the semantic (vector) memory layer using ChromaDB.
Falls back to SQLite FTS when ChromaDB is unavailable.
"""
import json
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class VectorMemoryStore:
    """Semantic memory using ChromaDB for vector similarity search.

    Provides:
    - add_document(): embed and store text with metadata
    - query(): semantic similarity search
    - delete(): remove documents
    Falls back to SQLite keyword search if ChromaDB/embeddings unavailable.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        collection_name: str = "synapse_memory",
        persist_directory: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._fallback_store: List[Dict] = []
        self._initialized = False

    async def _init(self) -> bool:
        """Initialize ChromaDB connection. Returns True if ChromaDB available."""
        if self._initialized:
            return self._client is not None
        self._initialized = True
        try:
            import chromadb  # noqa: PLC0415
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
            logger.warning("chromadb not installed — using in-memory keyword fallback")
            return False
        except Exception as e:
            logger.warning("ChromaDB init failed (%s) — using keyword fallback", e)
            return False

    def _embed_fallback(self, text: str) -> List[float]:
        """Deterministic hash-based embedding when LLM/ChromaDB unavailable."""
        import struct
        digest = hashlib.sha512(text.encode()).digest()
        raw = (digest * 6)[:768 * 4]
        values = struct.unpack(f">{768}f", raw)
        max_abs = max(abs(v) for v in values) or 1.0
        return [v / max_abs for v in values]

    async def add_document(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Embed and store a document."""
        doc_id = doc_id or hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
        meta = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "protocol_version": PROTOCOL_VERSION,
            **(metadata or {}),
        }
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                embedding = await self._get_embedding(text)
                self._collection.upsert(
                    ids=[doc_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[meta],
                )
                return doc_id
            except Exception as e:
                logger.warning("ChromaDB upsert failed: %s", e)
        # Fallback
        self._fallback_store.append({
            "id": doc_id, "text": text, "metadata": meta
        })
        return doc_id

    async def query(
        self,
        query_text: str,
        limit: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic similarity search."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                embedding = await self._get_embedding(query_text)
                kwargs: Dict[str, Any] = {
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
                return [
                    {
                        "text": doc,
                        "metadata": meta,
                        "score": round(1.0 - dist, 4),
                        "protocol_version": PROTOCOL_VERSION,
                    }
                    for doc, meta, dist in zip(docs, metas, dists)
                ]
            except Exception as e:
                logger.warning("ChromaDB query failed: %s", e)
        # Keyword fallback
        q_lower = query_text.lower()
        results = [
            {"text": item["text"], "metadata": item["metadata"], "score": 1.0, "protocol_version": PROTOCOL_VERSION}
            for item in self._fallback_store
            if q_lower in item["text"].lower()
        ]
        return results[:limit]

    async def delete(self, doc_id: str) -> bool:
        """Remove a document by ID."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                self._collection.delete(ids=[doc_id])
                return True
            except Exception as _exc:  # noqa
                pass  # noqa: silenced - _exc
        before = len(self._fallback_store)
        self._fallback_store = [d for d in self._fallback_store if d["id"] != doc_id]
        return len(self._fallback_store) < before

    async def count(self) -> int:
        """Return total document count."""
        chroma_ok = await self._init()
        if chroma_ok and self._collection is not None:
            try:
                return self._collection.count()
            except Exception as _exc:  # noqa
                pass  # noqa: silenced - _exc
        return len(self._fallback_store)

    async def _get_embedding(self, text: str) -> List[float]:
        """Get text embedding via litellm or fallback."""
        try:
            import litellm  # noqa: PLC0415
            response = litellm.embedding(model=self.embedding_model, input=[text])
            return response.data[0]["embedding"]
        except Exception:
            return self._embed_fallback(text)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "collection": self.collection_name,
            "backend": "chromadb" if self._client else "in_memory_keyword",
            "protocol_version": PROTOCOL_VERSION,
        }
