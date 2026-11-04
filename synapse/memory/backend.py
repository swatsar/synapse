"""Native MemoryBackend over Synapse's existing durable MemoryStore."""
from __future__ import annotations
import json, uuid
from synapse.memory.protocol import MemoryBackend, MemoryHit, MemoryKind, MemoryRecord, MemoryScope
from synapse.memory.store import MemoryStore

PROTOCOL_VERSION: str = "1.0"
class SynapseNativeMemory(MemoryBackend):
    def __init__(self, store:MemoryStore|None=None): self.store=store or MemoryStore()
    async def retain(self, record:MemoryRecord)->MemoryRecord:
        payload={"id":record.id,"scope":record.scope.key(),"kind":record.kind.value,"content":record.content,"metadata":record.metadata,"created_at":record.created_at}
        await self.store.add_episodic(f"memory:{record.scope.key()}:{record.id}",payload); return record
    async def recall(self, scope:MemoryScope, query:str, limit:int=10)->list[MemoryHit]:
        results=await self.store.search(query,limit=max(limit*3,limit)); hits=[]
        prefix=scope.key()
        for item in results:
            payload=item.get("data",item.get("value",{}));
            if not isinstance(payload,dict) or payload.get("scope")!=prefix: continue
            record=MemoryRecord(id=payload["id"],scope=scope,kind=MemoryKind(payload["kind"]),content=payload["content"],metadata=payload.get("metadata",{}),created_at=payload.get("created_at",""))
            hits.append(MemoryHit(record,1.0,"bm25_keyword"))
            if len(hits)>=limit: break
        return hits
    async def reflect(self, scope:MemoryScope, query:str)->str:
        hits=await self.recall(scope,query,limit=5)
        if not hits: return "No memories matched the query."
        return "\n".join(f"[{h.record.kind.value}] {h.record.content}" for h in hits)
