"""MemoryBackend protocol: retain, recall, reflect, separate from Knowledge."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
PROTOCOL_VERSION="1.0"
class MemoryKind(str,Enum):
    FACT="fact"; EPISODE="episode"; OBSERVATION="observation"; RELATIONSHIP="relationship"; DECISION="decision"; FAILURE="failure"; STRATEGY="successful_strategy"; MENTAL_MODEL="mental_model"
@dataclass(frozen=True)
class MemoryScope:
    tenant_id:str; user_id:str|None=None; workspace_id:str|None=None; project_id:str|None=None; agent_id:str|None=None
    def key(self)->str: return "/".join(x for x in [self.tenant_id,self.user_id,self.workspace_id,self.project_id,self.agent_id] if x)
@dataclass(frozen=True)
class MemoryRecord:
    id:str; scope:MemoryScope; kind:MemoryKind; content:str; metadata:dict[str,Any]=field(default_factory=dict); created_at:str=field(default_factory=lambda:datetime.now(UTC).isoformat())
@dataclass(frozen=True)
class MemoryHit:
    record:MemoryRecord; score:float; retrieval_mode:str
class MemoryBackend(ABC):
    @abstractmethod
    async def retain(self, record:MemoryRecord)->MemoryRecord: ...
    @abstractmethod
    async def recall(self, scope:MemoryScope, query:str, limit:int=10)->list[MemoryHit]: ...
    @abstractmethod
    async def reflect(self, scope:MemoryScope, query:str)->str: ...
