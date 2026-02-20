"""Tests for RAG System."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.rag import (
    RAGSystem,
    Document,
    RAGQuery,
    RAGResult,
    DocumentSensitivity,
    PROTOCOL_VERSION
)


class TestRAGProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        assert PROTOCOL_VERSION == "1.0"
    
    def test_system_has_protocol_version(self):
        assert RAGSystem.PROTOCOL_VERSION == "1.0"
    
    def test_document_has_protocol_version(self):
        doc = Document(content="test")
        assert doc.protocol_version == "1.0"
    
    def test_query_has_protocol_version(self):
        query = RAGQuery(query_text="test")
        assert query.protocol_version == "1.0"
    
    def test_result_has_protocol_version(self):
        result = RAGResult(documents=[], query="test", total_found=0)
        assert result.protocol_version == "1.0"


class TestRAGSystem:
    """Tests for RAGSystem."""
    
    @pytest.fixture
    def rag(self):
        return RAGSystem()
    
    @pytest.mark.asyncio
    async def test_add_document(self, rag):
        doc = Document(content="test content")
        doc_id = await rag.add_document(doc)
        assert doc_id is not None
        assert doc_id in rag.documents
    
    @pytest.mark.asyncio
    async def test_retrieve(self, rag):
        await rag.add_document(Document(content="test document"))
        query = RAGQuery(query_text="test", limit=5)
        result = await rag.retrieve(query)
        assert result.total_found >= 0
        assert result.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_sensitivity_filtering(self, rag):
        # Add public document
        await rag.add_document(Document(
            content="public doc",
            sensitivity_level=DocumentSensitivity.PUBLIC
        ))
        # Add confidential document
        await rag.add_document(Document(
            content="confidential doc",
            sensitivity_level=DocumentSensitivity.CONFIDENTIAL
        ))
        
        query = RAGQuery(query_text="doc", limit=10)
        result = await rag.retrieve(query)
        
        # Confidential should be filtered out
        for doc in result.documents:
            assert doc.sensitivity_level != DocumentSensitivity.CONFIDENTIAL


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        from synapse.integrations.rag import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
