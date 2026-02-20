PROTOCOL_VERSION: str = "1.0"
"""Network security layer – validates protocol version, node trust,
capability federation, replay protection and logs audit events.
"""
import hashlib
from typing import Any, Dict, List, Set

from synapse.security.capability_manager import CapabilityManager
from synapse.observability.logger import audit

class MessageSecurity:
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager):
        self._caps = caps
        # Simple replay protection – store hashes of recent messages
        self._seen_hashes: Set[str] = set()

    async def authorize_message(self, envelope: Dict[str, Any]) -> None:
        # Protocol version check
        if envelope.get("protocol_version") != self.protocol_version:
            audit(event="network_security", result="protocol_version_mismatch")
            raise ValueError("protocol_version mismatch")
        # Node trust – require a capability that represents trusted node
        await self._caps.check_capability(["node:trust"])
        # Capability federation – ensure envelope capabilities are allowed
        caps = envelope.get("capabilities", [])
        await self._caps.check_capability(caps)
        # Replay protection – hash of the envelope
        h = hashlib.sha256(str(envelope).encode()).hexdigest()
        if h in self._seen_hashes:
            audit(event="network_security", result="replay_detected")
            raise PermissionError("Replay attack detected")
        # Record hash (simple sliding window – keep last 1000)
        self._seen_hashes.add(h)
        if len(self._seen_hashes) > 1000:
            # Remove arbitrary element
            self._seen_hashes.pop()
        audit(event="network_security", result="authorized")
