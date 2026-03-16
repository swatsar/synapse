"""
Trust Identity Registry - Deterministic Node Identity
"""

import hashlib
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, UTC

PROTOCOL_VERSION = "1.0"


@dataclass
class NodeDescriptor:
    """Canonical node descriptor for identity registration"""
    node_id: str
    cluster_id: str
    capabilities: List[str]
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def canonicalize(self) -> str:
        """Produce canonical JSON representation"""
        data = {
            "node_id": self.node_id,
            "cluster_id": self.cluster_id,
            "capabilities": sorted(self.capabilities),
            "protocol_version": self.protocol_version
        }
        return json.dumps(data, sort_keys=True, separators=(',', ':'))


@dataclass
class NodeIdentity:
    """Cryptographic node identity"""
    node_id: str
    cluster_id: str
    identity_hash: str
    capabilities: List[str]
    protocol_version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class TrustIdentityRegistry:
    """
    Deterministic trust identity registry.
    Same descriptor always produces same identity hash.
    """

    PROTOCOL_VERSION = PROTOCOL_VERSION

    def __init__(self):
        self._identities: Dict[str, NodeIdentity] = {}
        self._registry_hash: Optional[str] = None

    def register(self, descriptor: NodeDescriptor) -> NodeIdentity:
        """Register node identity with deterministic hash"""
        canonical = descriptor.canonicalize()
        identity_hash = hashlib.sha256(canonical.encode()).hexdigest()

        identity = NodeIdentity(
            node_id=descriptor.node_id,
            cluster_id=descriptor.cluster_id,
            identity_hash=identity_hash,
            capabilities=descriptor.capabilities,
            protocol_version=self.PROTOCOL_VERSION
        )

        self._identities[descriptor.node_id] = identity
        self._update_registry_hash()

        return identity

    def get_identity(self, node_id: str) -> Optional[NodeIdentity]:
        """Retrieve registered identity"""
        return self._identities.get(node_id)

    def compute_registry_hash(self) -> str:
        """Compute hash of entire registry state"""
        if not self._identities:
            return hashlib.sha256(b"empty_registry").hexdigest()

        # Sort by node_id for determinism
        sorted_identities = sorted(
            self._identities.items(),
            key=lambda x: x[0]
        )

        registry_data = {
            "identities": [
                {
                    "node_id": node_id,
                    "identity_hash": identity.identity_hash
                }
                for node_id, identity in sorted_identities
            ],
            "protocol_version": self.PROTOCOL_VERSION
        }

        canonical = json.dumps(registry_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _update_registry_hash(self):
        """Update cached registry hash"""
        self._registry_hash = self.compute_registry_hash()
