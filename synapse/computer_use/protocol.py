from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from synapse.browser.protocol import CapabilityGuard
class ComputerUseBackend(ABC):
 @abstractmethod
 async def screen_read(self)->dict[str,Any]: ...
 @abstractmethod
 async def keyboard(self,text:str)->None: ...
class GuardedComputerUseBackend(ComputerUseBackend):
 def __init__(self,backend,guard:CapabilityGuard): self.backend=backend; self.guard=guard
 async def screen_read(self): await self.guard.require('computer:screen.read'); return await self.backend.screen_read()
 async def keyboard(self,text): await self.guard.require('computer:input.keyboard'); return await self.backend.keyboard(text)
