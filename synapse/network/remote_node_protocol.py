"""Remote node protocol – deterministic, capability‑gated, sandboxed.
All public models expose ``protocol_version = "1.0"``.
"""
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.core.time_sync_manager import TimeSyncManager

PROTOCOL_VERSION = "1.0"

class NodeIdentity(BaseModel):
    node_id: str
    protocol_version: str = PROTOCOL_VERSION
    capabilities: List[str] = []

    @field_validator("protocol_version")
    @classmethod
    def check_version(cls, v):
        if v != PROTOCOL_VERSION:
            raise ValueError("protocol_version mismatch")
        return v

class RemoteMessage(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = None  # filled by protocol
    timestamp: float = None
    node_id: str = None
    capabilities: List[str] = []
    payload: Any

    @field_validator("protocol_version")
    @classmethod
    def check_version(cls, v):
        if v != PROTOCOL_VERSION:
            raise ValueError("protocol_version mismatch")
        return v

    def normalise_timestamp(self):
        self.timestamp = TimeSyncManager.normalize(self.timestamp)

class HandshakeRequest(BaseModel):
    node_id: str
    protocol_version: str = PROTOCOL_VERSION
    capabilities: List[str] = []

    @field_validator("protocol_version")
    @classmethod
    def check_version(cls, v):
        if v != PROTOCOL_VERSION:
            raise ValueError("protocol_version mismatch")
        return v

class HandshakeResponse(BaseModel):
    node_id: str
    protocol_version: str = PROTOCOL_VERSION
    accepted: bool
    negotiated_capabilities: List[str] = []

    @field_validator("protocol_version")
    @classmethod
    def check_version(cls, v):
        if v != PROTOCOL_VERSION:
            raise ValueError("protocol_version mismatch")
        return v

class RemoteNodeProtocol:
    """High‑level protocol handling – handshake, capability negotiation,
    deterministic envelope creation and validation.
    """
    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, caps: CapabilityManager, node_id: str, limits=None):
        self._caps = caps
        self.node_id = node_id
        self.negotiated_capabilities: List[str] = []
        # ExecutionGuard is used for sandboxing when building envelopes
        self._guard = ExecutionGuard(capability_manager=caps)

    async def handle_handshake(self, request: HandshakeRequest) -> HandshakeResponse:
        # Validate protocol version – Pydantic already did it
        # Check that the remote node is trusted (capability check)
        await self._caps.check_capability(["handshake"])
        # Negotiate capabilities – for simplicity accept all requested
        self.negotiated_capabilities = request.capabilities
        # Return response
        return HandshakeResponse(
            node_id=self.node_id,
            accepted=True,
            negotiated_capabilities=self.negotiated_capabilities,
        )

    async def prepare_message(self, payload: Any) -> Dict[str, Any]:
        # Build a deterministic envelope inside the sandbox
        async with self._guard:
            # Get current time and convert to float timestamp
            now = TimeSyncManager.now()
            if hasattr(now, "timestamp"):
                ts = now.timestamp()
            else:
                ts = float(now)
            ts = TimeSyncManager.normalize(ts)
            
            return {
                "protocol_version": PROTOCOL_VERSION,
                "trace_id": str(uuid.uuid4()),
                "timestamp": ts,
                "node_id": self.node_id,
                "capabilities": self.negotiated_capabilities,
                "payload": payload,
            }

    async def validate_message(self, message: RemoteMessage) -> bool:
        # Validate incoming message
        if message.protocol_version != PROTOCOL_VERSION:
            return False
        # Normalise timestamp
        message.normalise_timestamp()
        return True
    
    async def validate_incoming(self, envelope: Dict[str, Any]) -> RemoteMessage:
        """Validate and parse incoming message envelope.
        
        Args:
            envelope: Message envelope dict
            
        Returns:
            RemoteMessage if valid
            
        Raises:
            ValueError: If validation fails
        """
        # Check required fields
        required = ["protocol_version", "trace_id", "timestamp", "node_id", "payload"]
        for field in required:
            if field not in envelope:
                raise ValueError(f"Missing required field: {field}")
        
        # Check protocol version
        if envelope["protocol_version"] != PROTOCOL_VERSION:
            raise ValueError(f"Protocol version mismatch: {envelope['protocol_version']}")
        
        # Check capabilities - must be in negotiated_capabilities
        capabilities = envelope.get("capabilities", [])
        for cap in capabilities:
            # First check if it's in negotiated capabilities from handshake
            if cap not in self.negotiated_capabilities:
                # Also check if CapabilityManager has it
                result = await self._caps.check_capability(cap)
                # Handle both bool and SecurityCheckResult return types
                approved = result if isinstance(result, bool) else result.approved
                if not approved:
                    raise PermissionError(f"Capability mismatch: missing {cap}")
        
        # Create RemoteMessage
        return RemoteMessage(
            protocol_version=envelope["protocol_version"],
            trace_id=envelope["trace_id"],
            timestamp=envelope["timestamp"],
            node_id=envelope["node_id"],
            capabilities=capabilities,
            payload=envelope["payload"]
        )
