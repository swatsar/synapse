PROTOCOL_VERSION: str = "1.0"
import asyncio
from typing import Dict

from synapse.connectors.base.connector import BaseConnector
from synapse.security.capability_manager import CapabilityManager

class TelegramConnector(BaseConnector):
    """Async Telegram connector – event‑driven stub.
    In production this would use `aiogram` or similar.
    """
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        self._incoming = asyncio.Queue()
        self._outgoing = asyncio.Queue()

    async def receive_message(self) -> Dict:
        # In a real bot this would await a webhook or polling.
        return await self._incoming.get()

    async def send_message(self, chat_id: int, text: str) -> None:
        # Simulate sending – push to outgoing queue for testing.
        await self._outgoing.put({"chat_id": chat_id, "text": text})

    # Helper used by tests to inject a message
    async def _inject(self, message: Dict) -> None:
        await self._incoming.put(message)
