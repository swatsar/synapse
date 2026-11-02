import pytest
from synapse.knowledge import KnowledgeBackend

@pytest.mark.asyncio
async def test_ingestion_retrieval_and_citation_provenance():
    kb = KnowledgeBackend()
    chunks = await kb.ingest('wiki', 'doc-1', 'Synapse uses a provider registry. The registry resolves credentials.', revision='r2', chunk_size=40)
    assert chunks[0].citation.source_id == 'wiki'
    hits = await kb.retrieve('provider registry')
    assert hits and hits[0].chunk.document_id == 'doc-1'
    assert hits[0].chunk.revision == 'r2'
    assert hits[0].chunk.citation.citation.startswith('doc-1#')
