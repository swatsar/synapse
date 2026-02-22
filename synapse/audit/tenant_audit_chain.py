"""
Tenant Audit Chain for Multi-Tenant Runtime
Append-only, cryptographically linked audit entries

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading


@dataclass
class AuditEntry:
    """Cryptographically linked audit entry"""
    entry_id: str
    tenant_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp: str
    previous_hash: str
    entry_hash: str
    protocol_version: str = "1.0"


class TenantAuditChain:
    """
    Append-only, cryptographically linked audit chain.

    Guarantees:
    - Append-only
    - Cryptographically linked entries
    - Tenant-scoped audit stream
    - Replay-verifiable
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._chains: Dict[str, List[AuditEntry]] = {}
        self._chain_roots: Dict[str, str] = {}
        self._lock = threading.Lock()

    def append(
        self,
        tenant_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> AuditEntry:
        """
        Append entry to tenant audit chain.

        Args:
            tenant_id: Tenant to append to
            event_type: Type of event
            event_data: Event data

        Returns:
            AuditEntry with cryptographic hash
        """
        with self._lock:
            # Initialize chain if needed
            if tenant_id not in self._chains:
                self._chains[tenant_id] = []
                self._chain_roots[tenant_id] = self._generate_genesis_hash(tenant_id)

            # Get previous hash
            chain = self._chains[tenant_id]
            previous_hash = chain[-1].entry_hash if chain else self._chain_roots[tenant_id]

            # Generate entry ID
            entry_id = self._generate_entry_id(tenant_id, len(chain))

            # Create entry
            entry = AuditEntry(
                entry_id=entry_id,
                tenant_id=tenant_id,
                event_type=event_type,
                event_data=event_data,
                timestamp=datetime.utcnow().isoformat(),
                previous_hash=previous_hash,
                entry_hash="",  # Will be calculated
                protocol_version=self.PROTOCOL_VERSION
            )

            # Calculate hash
            entry.entry_hash = self._hash_entry(entry)

            # Append to chain
            chain.append(entry)

            return entry

    def get_chain(self, tenant_id: str) -> List[AuditEntry]:
        """Get audit chain for tenant"""
        with self._lock:
            return self._chains.get(tenant_id, []).copy()

    def verify_chain(self, tenant_id: str) -> bool:
        """
        Verify cryptographic integrity of chain.

        Args:
            tenant_id: Tenant to verify

        Returns:
            True if chain is valid
        """
        with self._lock:
            if tenant_id not in self._chains:
                return True  # Empty chain is valid

            chain = self._chains[tenant_id]

            for i, entry in enumerate(chain):
                # Verify hash
                expected_hash = self._hash_entry(entry)
                if entry.entry_hash != expected_hash:
                    return False

                # Verify link
                if i == 0:
                    if entry.previous_hash != self._chain_roots[tenant_id]:
                        return False
                else:
                    if entry.previous_hash != chain[i-1].entry_hash:
                        return False

            return True

    def get_chain_root(self, tenant_id: str) -> str:
        """Get genesis hash for tenant chain"""
        with self._lock:
            if tenant_id not in self._chain_roots:
                return self._generate_genesis_hash(tenant_id)
            return self._chain_roots[tenant_id]

    def get_chain_tail(self, tenant_id: str) -> Optional[str]:
        """Get latest hash in chain"""
        with self._lock:
            if tenant_id not in self._chains or not self._chains[tenant_id]:
                return self._chain_roots.get(tenant_id)
            return self._chains[tenant_id][-1].entry_hash

    def _generate_entry_id(self, tenant_id: str, index: int) -> str:
        """Generate deterministic entry ID"""
        data = f"{tenant_id}:{index}:{self.PROTOCOL_VERSION}"
        return f"audit_{hashlib.sha256(data.encode()).hexdigest()[:16]}"

    def _generate_genesis_hash(self, tenant_id: str) -> str:
        """Generate genesis hash for tenant chain"""
        data = f"genesis:{tenant_id}:{self.PROTOCOL_VERSION}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _hash_entry(self, entry: AuditEntry) -> str:
        """Generate cryptographic hash of entry"""
        data = {
            "entry_id": entry.entry_id,
            "tenant_id": entry.tenant_id,
            "event_type": entry.event_type,
            "event_data": entry.event_data,
            "timestamp": entry.timestamp,
            "previous_hash": entry.previous_hash,
            "protocol_version": entry.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


class AuditHashTree:
    """
    Merkle tree structure for cluster-wide audit root.

    Guarantees:
    - Merkle structure
    - Cluster-wide audit root
    - Deterministic hash generation
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._tree_roots: Dict[str, str] = {}  # cluster_id -> root_hash
        self._tenant_leaves: Dict[str, Dict[str, str]] = {}  # cluster_id -> {tenant_id -> leaf_hash}
        self._lock = threading.Lock()

    def add_tenant_leaf(
        self,
        cluster_id: str,
        tenant_id: str,
        audit_chain: TenantAuditChain
    ) -> str:
        """
        Add tenant audit chain as leaf in tree.

        Args:
            cluster_id: Cluster identifier
            tenant_id: Tenant identifier
            audit_chain: Tenant audit chain

        Returns:
            Leaf hash
        """
        with self._lock:
            # Get chain tail
            tail_hash = audit_chain.get_chain_tail(tenant_id)
            if tail_hash is None:
                tail_hash = audit_chain.get_chain_root(tenant_id)

            # Initialize cluster if needed
            if cluster_id not in self._tenant_leaves:
                self._tenant_leaves[cluster_id] = {}

            # Add leaf
            self._tenant_leaves[cluster_id][tenant_id] = tail_hash

            # Recalculate root
            self._tree_roots[cluster_id] = self._calculate_root(cluster_id)

            return tail_hash

    def get_root(self, cluster_id: str) -> str:
        """Get Merkle root for cluster"""
        with self._lock:
            if cluster_id not in self._tree_roots:
                return self._empty_root(cluster_id)
            return self._tree_roots[cluster_id]

    def verify_leaf(
        self,
        cluster_id: str,
        tenant_id: str,
        leaf_hash: str
    ) -> bool:
        """Verify leaf is in tree"""
        with self._lock:
            if cluster_id not in self._tenant_leaves:
                return False
            return self._tenant_leaves[cluster_id].get(tenant_id) == leaf_hash

    def _calculate_root(self, cluster_id: str) -> str:
        """Calculate Merkle root from leaves"""
        if cluster_id not in self._tenant_leaves:
            return self._empty_root(cluster_id)

        leaves = self._tenant_leaves[cluster_id]
        if not leaves:
            return self._empty_root(cluster_id)

        # Sort tenant IDs for deterministic ordering
        sorted_hashes = [leaves[tid] for tid in sorted(leaves.keys())]

        # Build Merkle tree
        while len(sorted_hashes) > 1:
            new_level = []
            for i in range(0, len(sorted_hashes), 2):
                if i + 1 < len(sorted_hashes):
                    combined = f"{sorted_hashes[i]}:{sorted_hashes[i+1]}"
                else:
                    combined = f"{sorted_hashes[i]}:{sorted_hashes[i]}"
                new_level.append(hashlib.sha256(combined.encode()).hexdigest())
            sorted_hashes = new_level

        return sorted_hashes[0]

    def _empty_root(self, cluster_id: str) -> str:
        """Generate empty root hash"""
        data = f"empty:{cluster_id}:{self.PROTOCOL_VERSION}"
        return hashlib.sha256(data.encode()).hexdigest()


__all__ = ["TenantAuditChain", "AuditHashTree", "AuditEntry"]
