PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Any, Dict, List

from synapse.agents.runtime.agent import RuntimeAgent
from synapse.security.capability_manager import CapabilityManager

class NodeRuntime:
    """Executes a set of RuntimeAgents in an isolated async context.
    Agents communicate through an event queue; the runtime enforces
    capability checks before forwarding events.
    """
    protocol_version: str = "1.0"

    def __init__(self, agents: List[RuntimeAgent], caps: CapabilityManager):
        self._agents = agents
        self._caps = caps
        self._event_queue: asyncio.Queue[Dict] = asyncio.Queue()

    async def _dispatch(self, event: Dict) -> None:
        # Simple broadcast – in a real system this could be routing logic
        for ag in self._agents:
            await ag.handle_event(event)

    async def run(self) -> None:
        # Start all agents
        async with asyncio.TaskGroup() as tg:
            for ag in self._agents:
                tg.create_task(ag.run())
            # Event loop – pull from queue and broadcast
            while True:
                ev = await self._event_queue.get()
                # Capability check for the event source
                await self._caps.check_capability(ev.get("required_capabilities", []))
                await self._dispatch(ev)

    async def post_event(self, event: Dict) -> None:
        await self._event_queue.put(event)
