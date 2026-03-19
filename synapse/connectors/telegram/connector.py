"""Telegram Connector — real aiogram 3.x integration.

Protocol Version: 1.0
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional, Callable

from synapse.connectors.base.connector import BaseConnector
from synapse.security.capability_manager import CapabilityManager

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class TelegramConnector(BaseConnector):
    """Telegram bot connector using aiogram 3.x.

    In production: configure TELEGRAM_BOT_TOKEN env var.
    Falls back to in-memory queue for testing when token is absent.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        caps: CapabilityManager,
        token: Optional[str] = None,
        on_message: Optional[Callable] = None,
    ):
        self._caps = caps
        self._token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._on_message = on_message
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._outgoing: asyncio.Queue = asyncio.Queue()
        self._bot = None
        self._dp = None
        self._running = False

    async def start(self) -> None:
        """Start the bot (polling or webhook)."""
        if not self._token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — running in stub mode")
            return
        try:
            from aiogram import Bot, Dispatcher
            from aiogram.filters import Command
            from aiogram.types import Message

            self._bot = Bot(token=self._token)
            self._dp = Dispatcher()

            @self._dp.message()
            async def handle(message: Message) -> None:
                event = {
                    "source": "telegram",
                    "chat_id": message.chat.id,
                    "user_id": message.from_user.id if message.from_user else None,
                    "text": message.text or "",
                    "message_id": message.message_id,
                    "protocol_version": PROTOCOL_VERSION,
                }
                await self._incoming.put(event)
                if self._on_message:
                    await self._on_message(event)

            self._running = True
            asyncio.create_task(self._dp.start_polling(self._bot, handle_signals=False))
            logger.info("Telegram bot started (polling)")
        except ImportError:
            logger.warning("aiogram not installed — Telegram connector in stub mode")
        except Exception as e:
            logger.error(f"Telegram start failed: {e}")

    async def stop(self) -> None:
        if self._dp and self._running:
            await self._dp.stop_polling()
            self._running = False
        if self._bot:
            await self._bot.session.close()

    async def receive_message(self) -> Dict[str, Any]:
        """Block until a message arrives."""
        return await self._incoming.get()

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a chat."""
        if self._bot:
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
                return
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
        # Fallback: push to outgoing queue (test/stub mode)
        await self._outgoing.put({"chat_id": chat_id, "text": text})

    async def send_approval_request(
        self,
        chat_id: int,
        description: str,
        approval_id: str,
        risk_level: int,
        code_preview: Optional[str] = None,
    ) -> None:
        """Send a human-approval request with inline keyboard."""
        text = (
            f"⚠️ *Требуется одобрение*\n\n"
            f"**Действие:** {description}\n"
            f"**Уровень риска:** {risk_level}/5\n"
            f"**ID:** `{approval_id}`\n"
        )
        if code_preview:
            text += f"\n```python\n{code_preview[:500]}\n```"
        text += f"\n\nОтветьте `/approve {approval_id}` или `/reject {approval_id}`"

        if self._bot:
            try:
                from aiogram.utils.markdown import markdown_decoration
                await self._bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                return
            except Exception as e:
                logger.error(f"Approval request send failed: {e}")
        await self._outgoing.put({"chat_id": chat_id, "text": text, "approval_id": approval_id})

    # ── Test helpers ──────────────────────────────────────────────────────────

    async def _inject(self, message: Dict[str, Any]) -> None:
        """Inject a message for testing."""
        await self._incoming.put(message)

    async def _drain_outgoing(self) -> list:
        """Drain outgoing queue for test assertions."""
        messages = []
        while not self._outgoing.empty():
            messages.append(self._outgoing.get_nowait())
        return messages
