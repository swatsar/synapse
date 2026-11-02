import pytest
from synapse.memory import MemoryKind, MemoryRecord, MemoryScope, SynapseNativeMemory

@pytest.mark.asyncio
async def test_retain_recall_reflect_is_scope_aware():
    memory=SynapseNativeMemory(); scope=MemoryScope('t1',workspace_id='w1',agent_id='a1')
    other=MemoryScope('t1',workspace_id='w2',agent_id='a2')
    await memory.retain(MemoryRecord('m1',scope,MemoryKind.FACT,'deployment uses postgres'))
    await memory.retain(MemoryRecord('m2',other,MemoryKind.FACT,'deployment uses postgres'))
    hits=await memory.recall(scope,'postgres')
    assert [h.record.id for h in hits]==['m1']
    assert hits[0].retrieval_mode=='bm25_keyword'
    assert 'postgres' in await memory.reflect(scope,'postgres')
    await memory.store.close()

@pytest.mark.asyncio
async def test_no_semantic_hash_fallback():
    from synapse.llm.provider import EmbeddingUnavailable, LiteLLMProvider
    with pytest.raises(EmbeddingUnavailable):
        await LiteLLMProvider('missing','missing-model').embed('text')
