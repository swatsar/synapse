"""Minimal KnowledgeBackend boundary: documentary knowledge, not agent memory."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
import re, uuid
from typing import Any
@dataclass(frozen=True)
class Citation:
 source_id:str; document_id:str; revision:str; chunk_id:str; citation:str
@dataclass(frozen=True)
class KnowledgeChunk:
 id:str; source_id:str; document_id:str; revision:str; content:str; citation:Citation; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class KnowledgeHit:
 chunk:KnowledgeChunk; retrieval_score:float; rerank_score:float|None=None; retrieval_mode:str='bm25'
class KnowledgeBackend:
 def __init__(self): self._chunks:dict[str,KnowledgeChunk]={}
 async def ingest(self, source_id:str, document_id:str, content:str, revision:str='1', chunk_size:int=1000)->list[KnowledgeChunk]:
  chunks=[]
  for i in range(0,len(content),chunk_size):
   text=content[i:i+chunk_size]; cid=f'{document_id}:{revision}:{i//chunk_size}'; citation=Citation(source_id,document_id,revision,cid,f'{document_id}#{i//chunk_size+1}')
   chunk=KnowledgeChunk(cid,source_id,document_id,revision,text,citation); self._chunks[cid]=chunk; chunks.append(chunk)
  return chunks
 async def retrieve(self, query:str, limit:int=5)->list[KnowledgeHit]:
  terms=set(re.findall(r'[\w-]+',query.lower())); hits=[]
  for c in self._chunks.values():
   score=sum(1 for t in terms if t in c.content.lower())
   if score: hits.append(KnowledgeHit(c,float(score),float(score),'bm25'))
  return sorted(hits,key=lambda h:h.rerank_score or h.retrieval_score,reverse=True)[:limit]
