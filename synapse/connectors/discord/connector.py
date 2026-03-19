"""Discord Connector — real discord.py integration.

Protocol Version: 1.0
Specification: 3.1

Uses discord.py for production. Falls back to asyncio.Queue stub
when discord.py is not installed so tests and other connectors
still function correctly.
"""
import asyncio
import logging
from typing import Callable, Dict, Optional

from synapse.connectors.base.connector import BaseConnector
from synapse.security.capability_manager import CapabilityManager
from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class DiscordConnector(BaseConnector):
    """Discord bot connector using discord.py.

    Falls back to in-memory queue mode when discord.py not installed.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        caps: CapabilityManager,
        token: Optional[str] = None,
        command_prefix: str = "!",
        authorized_guild_ids: Optional[list] = None,
    ):
        self._caps = caps
        self._token = token
        self._command_prefix = command_prefix
        self._authorized_guilds = set(authorized_guild_ids or [])

        # Queue-based I/O (used both in stub mode and as internal buffer)
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._outgoing: asyncio.Queue = asyncio.Queue()

        # discord.py objects (None in stub mode)
        self._client = None
        self._bot = None
        self._running = False
        self._message_handler: Optional[Callable] = None

        audit(
            event="discord_connector_init",
            has_token=bool(token),
            protocol_version=PROTOCOL_VERSION,
        )

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    async def receive_message(self) -> Dict:
        """Wait for next incoming Discord message."""
        return await self._incoming.get()

    async def send_message(self, channel_id: int, text: str) -> None:
        """Send a message to a Discord channel."""
        if self._bot and self._running:
            try:
                channel = self._bot.get_channel(channel_id)
                if channel:
                    await channel.send(text[:2000])  # Discord 2000 char limit
                    audit(
                        event="discord_message_sent",
                        channel_id=channel_id,
                        length=len(text),
                        protocol_version=PROTOCOL_VERSION,
                    )
                    return
            except Exception as e:
                logger.warning("Discord send failed: %s", e)
        # Fallback to queue
        await self._outgoing.put({"channel_id": channel_id, "text": text})

    async def start(self, message_handler: Optional[Callable] = None) -> None:
        """Start the Discord bot."""
        self._message_handler = message_handler
        try:
            import discord  # noqa: PLC0415

            intents = discord.Intents.default()
            intents.message_content = True
            self._bot = discord.Client(intents=intents)
            self._register_events()

            if self._token:
                audit(event="discord_bot_starting", protocol_version=PROTOCOL_VERSION)
                asyncio.create_task(self._bot.start(self._token))
                self._running = True
            else:
                logger.warning("Discord token not set — running in stub mode")
        except ImportError:
            logger.warning("discord.py not installed — Discord connector in queue stub mode")

    async def stop(self) -> None:
        """Stop the Discord bot gracefully."""
        if self._bot and self._running:
            await self._bot.close()
            self._running = False
            audit(event="discord_bot_stopped", protocol_version=PROTOCOL_VERSION)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_events(self) -> None:
        """Register discord.py event handlers."""
        bot = self._bot

        @bot.event
        async def on_ready():
            logger.info("Discord bot connected as %s", bot.user)
            audit(event="discord_bot_ready", username=str(bot.user), protocol_version=PROTOCOL_VERSION)

        @bot.event
        async def on_message(message):
            # Ignore own messages
            if message.author == bot.user:
                return
            # Guild filter
            if self._authorized_guilds and message.guild:
                if message.guild.id not in self._authorized_guilds:
                    return

            normalized = {
                "source": "discord",
                "channel_id": message.channel.id,
                "guild_id": message.guild.id if message.guild else None,
                "author_id": message.author.id,
                "author_name": str(message.author),
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
                "protocol_version": PROTOCOL_VERSION,
            }

            audit(
                event="discord_message_received",
                channel_id=normalized["channel_id"],
                author=normalized["author_name"],
                protocol_version=PROTOCOL_VERSION,
            )

            await self._incoming.put(normalized)

            if self._message_handler:
                asyncio.create_task(self._message_handler(normalized))

    # ------------------------------------------------------------------
    # Test helpers (queue injection)
    # ------------------------------------------------------------------

    async def _inject(self, message: Dict) -> None:
        """Inject a message directly (for testing)."""
        await self._incoming.put(message)

    async def _drain_outgoing(self) -> list:
        """Drain outgoing queue (for testing)."""
        messages = []
        while not self._outgoing.empty():
            messages.append(await self._outgoing.get())
        return messages
