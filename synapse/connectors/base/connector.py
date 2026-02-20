PROTOCOL_VERSION: str = "1.0"
"""BaseConnector – abstract async interface for messenger connectors.

All concrete connectors (Telegram, Discord, etc.) must inherit from this
class and implement the two core coroutine methods:

* ``receive_message`` – await the next inbound message and return a dict.
* ``send_message`` – send a message to the external service.

The class also defines a ``protocol_version`` constant ("1.0") to satisfy the
projectwide requirement that every public model expose a protocol version.
"""

import abc
from typing import Dict, Any

class BaseConnector(abc.ABC):
    """Abstract base class for all messenger connectors.

    Sub‑classes are expected to be fully async and to respect the
    ``CapabilityManager`` checks performed by the caller before invoking
    ``receive_message`` or ``send_message``.
    """
    protocol_version: str = "1.0"

    @abc.abstractmethod
    async def receive_message(self) -> Dict[str, Any]:
        """Wait for the next inbound message and return it as a dictionary."""
        ...

    @abc.abstractmethod
    async def send_message(self, *args, **kwargs) -> None:
        """Send a message to the external service.

        Concrete implementations decide on the signature (e.g., ``chat_id``
        and ``text`` for Telegram, ``channel_id`` for Discord).
        """
        ...
