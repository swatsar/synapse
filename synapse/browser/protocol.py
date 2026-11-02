"""Capability-gated browser/computer backend protocols."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
class CapabilityDenied(PermissionError): pass
@dataclass(frozen=True)
class BrowserSession: id:str; owner_id:str; url:str|None=None
class BrowserBackend(ABC):
 @abstractmethod
 async def open(self,owner_id:str,url:str)->BrowserSession: ...
 @abstractmethod
 async def read(self,session:BrowserSession)->dict[str,Any]: ...
class CapabilityGuard:
 def __init__(self,check): self.check=check
 async def require(self,capability:str,context:Any=None):
  result=await self.check(context=context,required=capability)
  if hasattr(result,'approved') and not result.approved: raise CapabilityDenied(capability)
  if result is False: raise CapabilityDenied(capability)
class GuardedBrowserBackend(BrowserBackend):
 def __init__(self,backend:BrowserBackend,guard:CapabilityGuard): self.backend=backend; self.guard=guard
 async def open(self,owner_id,url): await self.guard.require('browser:navigate'); return await self.backend.open(owner_id,url)
 async def read(self,session): await self.guard.require('browser:read'); return await self.backend.read(session)
