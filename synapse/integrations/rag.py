"""
RAG System for Synapse.

Adapted from LangChain RAG patterns:
https://github.com/langchain-ai/langchain

Original License: MIT
Adaptation: Added security filtering, protocol versioning,
           capability validation, audit logging

Copyright (c) 2024 LangChain, Inc.
Copyright (c) 2026 Synapse Contributors
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PROTOCOL_VERSION: str = "1.0"


class DocumentSensitivity(str, Enum):
    """Sensitivity level of document"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


@dataclass
class Document:
    """Document for RAG system"""
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    embedding: list[float] | None = None
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    source_verified: bool = False
    sensitivity_level: DocumentSensitivity = DocumentSensitivity.PUBLIC


@dataclass
class RAGQuery:
    """Query for RAG retrieval"""
    query_text: str
    limit: int = 5
    memory_types: list[str] = field(default_factory=list)
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = ""


@dataclass
class RAGResult:
    """Result from RAG retrieval"""
    documents: list[Document]
    query: str
    total_found: int
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = ""


class RAGSystem:
    """
    Retrieval-Augmented Generation system.
    
    Adapted from LangChain RAG patterns with Synapse security enhancements.
    
    Features:
    - Document storage with sensitivity classification
    - Semantic search with security filtering
    - Capability-based access control
    - Audit logging for all queries
    """
    
    PROTOCOL_VERSION: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        vector_store: Any = None,
        llm_provider: Any = None,
        security_manager: Any = None,
        audit_logger: Any = None
    ):
        self.vector_store = vector_store
        self.llm = llm_provider
        self.security = security_manager
        self.audit = audit_logger
        self.documents: dict[str, Document] = {}
    
    async def add_document(self, document: Document) -> str:
        """Add document to RAG system"""
        import uuid
        doc_id = document.id or str(uuid.uuid4())
        document.id = doc_id
        
        # Generate embedding
        if self.llm and not document.embedding:
            document.embedding = await self._generate_embedding(document.content)
        
        # Store document
        self.documents[doc_id] = document
        
        if self.vector_store:
            await self.vector_store.add(document)
        
        if self.audit:
            await self.audit.log_action(
                action="rag_document_added",
                result={"doc_id": doc_id, "sensitivity": document.sensitivity_level.value},
                context={"protocol_version": self.PROTOCOL_VERSION}
            )
        
        return doc_id
    
    async def retrieve(self, query: RAGQuery, context: dict[str, Any] | None = None) -> RAGResult:
        """Retrieve documents, using vectors only when a real backend exists."""
        query_embedding = await self._generate_embedding(query.query_text)
        if self.vector_store and query_embedding is not None:
            results = await self.vector_store.search(query_embedding, query.limit)
        else:
            results = self._lexical_search(query.query_text, query.limit)
        filtered = await self._filter_by_sensitivity(results, context or {})
        if self.audit:
            await self.audit.log_action(
                action="rag_query",
                result={"query": query.query_text, "results": len(filtered)},
                context={"trace_id": query.trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
        return RAGResult(documents=filtered, query=query.query_text,
                         total_found=len(filtered), trace_id=query.trace_id,
                         protocol_version=self.PROTOCOL_VERSION)

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Return a real embedding, or None for lexical degradation."""
        if self.llm and hasattr(self.llm, "embed"):
            try:
                return await self.llm.embed(text)
            except Exception:
                return None
        return None

    def _lexical_search(self, query: str, limit: int) -> list[Document]:
        terms = set(query.lower().split())
        ranked = []
        for document in self.documents.values():
            score = sum(term in document.content.lower() for term in terms)
            if score:
                ranked.append((score, document))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [document for _, document in ranked[:limit]]

    async def _filter_by_sensitivity(
        self,
        documents: list[Document],
        context: dict[str, Any]
    ) -> list[Document]:
        """Filter documents by sensitivity level"""
        filtered = []
        for doc in documents:
            if doc.sensitivity_level == DocumentSensitivity.PUBLIC:
                filtered.append(doc)
            elif doc.sensitivity_level == DocumentSensitivity.INTERNAL:
                if self.security and context:
                    has_access = await self.security.check_capabilities(
                        required=["memory:internal"],
                        context=context
                    )
                    if has_access.get("approved", False):
                        filtered.append(doc)
            # Confidential documents not returned via RAG
        return filtered



SKILL_MANIFEST = {
    "name": "rag_system",
    "version": "1.0.0",
    "description": "Retrieval-Augmented Generation system",
    "author": "synapse_core",
    "inputs": {
        "query": "str",
        "limit": "int"
    },
    "outputs": {
        "documents": "list",
        "total_found": "int"
    },
    "required_capabilities": ["memory:read"],
    "risk_level": 2,
    "isolation_type": "subprocess",
    "protocol_version": PROTOCOL_VERSION
}
