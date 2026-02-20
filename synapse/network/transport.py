PROTOCOL_VERSION: str = "1.0"
"""Async transport abstraction – deterministic, capability‑gated, audited.
All public methods are async and respect ExecutionGuard, CapabilityManager and
resource limits.
"""
import asyncio
import json
from typing import Any, Dict, List

from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.observability.logger import audit

class Transport:
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager, guard: ExecutionGuard):
        self._caps = caps
        self._guard = guard
        # In‑memory queue used for the stub implementation – in prod this would be a socket
        self._outbox: List[Dict] = []
        self._inbox: List[Dict] = []

    async def _send(self, envelope: Dict[str, Any]) -> None:
        # Simulated low‑level send – just push to inbox of the remote side
        self._outbox.append(envelope)

    async def _receive(self) -> Dict[str, Any]:
        # Simulated low‑level receive – pop from inbox
        while not self._inbox:
            await asyncio.sleep(0.01)
        return self._inbox.pop(0)

    async def send_message(self, envelope: Dict[str, Any], required_caps: List[str] = None) -> None:
        # Capability check before sending
        caps = required_caps or envelope.get("capabilities", [])
        await self._caps.check_capability(caps)
        # Resource accounting – we rely on ExecutionGuard for sandboxing
        async with self._guard:
            # Deterministic serialization – sorted keys
            serialized = json.dumps(envelope, sort_keys=True)
            # Audit log
            audit(event="network_send", payload=serialized)
            # Simulated send (store in outbox)
            await self._send(envelope)

    async def receive_message(self, timeout: float = 5.0) -> Dict[str, Any]:
        try:
            # Timeout handling
            envelope = await asyncio.wait_for(self._receive(), timeout=timeout)
        except asyncio.TimeoutError:
            audit(event="network_receive_timeout", detail="no message within timeout")
            raise
        # Audit log
        audit(event="network_receive", payload=json.dumps(envelope, sort_keys=True))
        return envelope

    # Helper for tests to inject a message into the inbox
    def inject_incoming(self, envelope: Dict[str, Any]) -> None:
        self._inbox.append(envelope)
