"""Capability-Based Permission System.

Protocol Version: 1.0
Specification: 3.1

Implements the CapabilityScope enum as defined in the architecture spec.
Each capability is a typed token that grants specific, scoped access.
Follows the Principle of Least Privilege.
"""
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import uuid

PROTOCOL_VERSION: str = "1.0"


class CapabilityScope(str, Enum):
    """Typed capability scopes per architecture specification.

    Format: namespace:action[:path]
    Example: fs:read:/workspace/**

    These are non-executable tokens that represent specific permissions.
    """
    # Filesystem
    FILESYSTEM_READ = "fs:read"
    FILESYSTEM_WRITE = "fs:write"
    FILESYSTEM_DELETE = "fs:delete"
    FILESYSTEM_EXECUTE = "fs:execute"

    # Network
    NETWORK_HTTP = "net:http"
    NETWORK_SCAN = "net:scan"
    NETWORK_LISTEN = "net:listen"

    # OS Process
    PROCESS_SPAWN = "os:process"
    PROCESS_KILL = "os:kill"

    # IoT / Devices
    DEVICE_IOT = "iot:control"
    DEVICE_READ = "iot:read"

    # System
    SYSTEM_INFO = "sys:info"
    SYSTEM_CONFIG = "sys:config"
    SYSTEM_SHUTDOWN = "sys:shutdown"

    # Memory
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_INTERNAL = "memory:internal"

    # Code / Skills
    CODE_GENERATE = "code:generate"
    CODE_EXECUTE = "code:execute"
    CODE_INSTALL = "code:install"

    # Consensus / Cluster
    CONSENSUS_PROPOSE = "consensus:propose"
    CONSENSUS_DECIDE = "consensus:decide"
    COORDINATION_REGISTER = "coordination:register"
    COORDINATION_BROADCAST = "coordination:broadcast"
    COORDINATION_READ = "coordination:read"

    # Cluster / Snapshot
    CLUSTER_SNAPSHOT = "cluster:snapshot"
    CLUSTER_ROLLBACK = "cluster:rollback"


# Risk levels per capability (1=low, 5=critical)
CAPABILITY_RISK_LEVELS = {
    CapabilityScope.FILESYSTEM_READ: 1,
    CapabilityScope.FILESYSTEM_WRITE: 2,
    CapabilityScope.FILESYSTEM_DELETE: 4,
    CapabilityScope.FILESYSTEM_EXECUTE: 5,
    CapabilityScope.NETWORK_HTTP: 2,
    CapabilityScope.NETWORK_SCAN: 4,
    CapabilityScope.NETWORK_LISTEN: 3,
    CapabilityScope.PROCESS_SPAWN: 4,
    CapabilityScope.PROCESS_KILL: 5,
    CapabilityScope.DEVICE_IOT: 3,
    CapabilityScope.DEVICE_READ: 1,
    CapabilityScope.SYSTEM_INFO: 1,
    CapabilityScope.SYSTEM_CONFIG: 3,
    CapabilityScope.SYSTEM_SHUTDOWN: 5,
    CapabilityScope.MEMORY_READ: 1,
    CapabilityScope.MEMORY_WRITE: 2,
    CapabilityScope.MEMORY_INTERNAL: 2,
    CapabilityScope.CODE_GENERATE: 3,
    CapabilityScope.CODE_EXECUTE: 5,
    CapabilityScope.CODE_INSTALL: 4,
    CapabilityScope.CONSENSUS_PROPOSE: 2,
    CapabilityScope.CONSENSUS_DECIDE: 2,
    CapabilityScope.COORDINATION_REGISTER: 2,
    CapabilityScope.COORDINATION_BROADCAST: 2,
    CapabilityScope.COORDINATION_READ: 1,
    CapabilityScope.CLUSTER_SNAPSHOT: 2,
    CapabilityScope.CLUSTER_ROLLBACK: 3,
}


@dataclass
class CapabilityToken:
    """A scoped capability token.

    Non-executable. Can be granted, revoked, and checked.
    Has optional path constraint and TTL.
    """
    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scope: CapabilityScope = CapabilityScope.FILESYSTEM_READ
    path_constraint: Optional[str] = None   # e.g. "/workspace/**"
    issued_to: str = "agent"
    issued_by: str = "system"
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    @property
    def full_scope(self) -> str:
        """Return full scoped capability string."""
        if self.path_constraint:
            return f"{self.scope.value}:{self.path_constraint}"
        return self.scope.value

    @property
    def risk_level(self) -> int:
        """Return risk level for this capability."""
        return CAPABILITY_RISK_LEVELS.get(self.scope, 3)

    def is_expired(self) -> bool:
        """Check if token has expired."""
        if not self.expires_at:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expires

    def matches(self, required_scope: str) -> bool:
        """Check if this token satisfies a required scope string."""
        import fnmatch
        full = self.full_scope
        # Exact match
        if full == required_scope:
            return True
        # Wildcard match (e.g. token has fs:read:/workspace/**, required is fs:read:/workspace/file.txt)
        if "*" in full:
            return fnmatch.fnmatch(required_scope, full)
        # Prefix match (e.g. token "fs:read" covers "fs:read:/workspace/file")
        if required_scope.startswith(full):
            return True
        return False

    def to_dict(self):
        return {
            "token_id": self.token_id,
            "scope": self.scope.value,
            "full_scope": self.full_scope,
            "path_constraint": self.path_constraint,
            "issued_to": self.issued_to,
            "issued_by": self.issued_by,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "risk_level": self.risk_level,
            "protocol_version": self.protocol_version,
        }


def make_token(
    scope: CapabilityScope,
    issued_to: str,
    issued_by: str = "orchestrator",
    path: Optional[str] = None,
    ttl_hours: Optional[int] = None,
) -> CapabilityToken:
    """Factory for creating capability tokens."""
    expires_at = None
    if ttl_hours:
        expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        expires_at = expires.isoformat()
    return CapabilityToken(
        scope=scope,
        path_constraint=path,
        issued_to=issued_to,
        issued_by=issued_by,
        expires_at=expires_at,
    )


# Default safe capability set for new agents
DEFAULT_AGENT_CAPABILITIES: List[CapabilityScope] = [
    CapabilityScope.FILESYSTEM_READ,
    CapabilityScope.MEMORY_READ,
    CapabilityScope.MEMORY_WRITE,
    CapabilityScope.SYSTEM_INFO,
    CapabilityScope.NETWORK_HTTP,
]
