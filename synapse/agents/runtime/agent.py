PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Any, Callable, Dict, List

from synapse.core.models import ExecutionContext, SkillManifest
from synapse.observability.logger import trace, record_metric

class CognitiveAgent:
    """Base class for cognitive agents.
    Implements the classic loop: perceive → reason → act → learn.
    Skills are looked up via a simple registry dictionary.
    """
    def __init__(self, name: str, context: ExecutionContext):
        self.name = name
        self.context = context
        self.skill_registry: Dict[str, Callable[..., Any]] = {}

    # ---------------------------------------------------------------------
    # Skill handling
    # ---------------------------------------------------------------------
    def register_skill(self, manifest: SkillManifest, handler: Callable[..., Any]):
        self.skill_registry[manifest.name] = handler
        record_metric("skill_registered")

    async def execute_skill(self, name: str, **kwargs):
        if name not in self.skill_registry:
            raise ValueError(f"Skill {name} not registered")
        handler = self.skill_registry[name]
        async with trace("skill_execute", skill=name):
            result = await handler(**kwargs)
            record_metric("skill_executed")
            return result

    # ---------------------------------------------------------------------
    # Lifecycle hooks – default implementations are no‑ops
    # ---------------------------------------------------------------------
    async def perceive(self) -> Any:
        async with trace("perceive"):
            # In a real system this would ingest events from connectors
            return None

    async def reason(self, perception: Any) -> Any:
        async with trace("reason"):
            # Decision making – placeholder returns a dummy plan
            return {"action": "noop"}

    async def act(self, plan: Any) -> Any:
        async with trace("act"):
            # Execute a skill if plan specifies one
            if isinstance(plan, dict) and plan.get("action") == "skill":
                return await self.execute_skill(plan["skill_name"], **plan.get("params", {}))
            return None

    async def learn(self, result: Any) -> None:
        async with trace("learn"):
            # Placeholder – could store experience in memory
            pass

    # ---------------------------------------------------------------------
    # Full run – orchestrates the lifecycle
    # ---------------------------------------------------------------------
    async def run_once(self):
        perception = await self.perceive()
        plan = await self.reason(perception)
        result = await self.act(plan)
        await self.learn(result)
        return result
# Compatibility alias for historic imports
RuntimeAgent = CognitiveAgent
