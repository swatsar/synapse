"""Execution-only HarnessAdapter; Synapse remains orchestration owner."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
PROTOCOL_VERSION="1.0"
@dataclass(frozen=True)
class HarnessRequest:
 task_id:str; run_id:str; prompt:str; workspace_id:str|None=None; capabilities:tuple[str,...]=(); budget_usd:float|None=None; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class HarnessResult:
 success:bool; output:str=""; artifacts:tuple[str,...]=(); error:str|None=None; usage:dict[str,Any]=field(default_factory=dict)
class HarnessAdapter(ABC):
 name="abstract"
 @abstractmethod
 async def execute(self, request:HarnessRequest)->HarnessResult: ...
class UnconfiguredHarness(HarnessAdapter):
 def __init__(self,name:str): self.name=name
 async def execute(self,request): return HarnessResult(False,error=f"harness {self.name} is not configured")
class CodexHarness(UnconfiguredHarness):
 def __init__(self): super().__init__('codex')
class ClaudeCodeHarness(UnconfiguredHarness):
 def __init__(self): super().__init__('claude_code')
class HermesHarness(UnconfiguredHarness):
 def __init__(self): super().__init__('hermes')
class AgentZeroHarness(UnconfiguredHarness):
 def __init__(self): super().__init__('agent_zero')
