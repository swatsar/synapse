PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Dict

from synapse.connectors.base.connector import BaseConnector
from synapse.security.capability_manager import CapabilityManager

class DiscordConnector(BaseConnector):
    """Async Discord connector – event‑driven stub.
    In production this would use `discord.py`.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._incoming = asyncio.Queue()
        self._outgoing = asyncio.Queue()

    async def receive_message(self) -> Dict:
        return await self._incoming.get()

    async def send_message(self, channel_id: int, text: str) -> None:
        await self._outgoing.put({"channel_id": channel_id, "text": text})

    async def _inject(self, message: Dict) -> None:
        await self._incoming.put(message)
