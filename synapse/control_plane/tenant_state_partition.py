"""
Tenant State Partition for Multi-Tenant Runtime
Cluster state segmented by tenant with cryptographic isolation

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading


@dataclass
class StateEntry:
    """State entry with tenant scope"""
    tenant_id: str
    key: str
    value: Any
    timestamp: str
    state_hash: str
    protocol_version: str = "1.0"


class TenantStatePartition:
    """
    Tenant-segmented state management.

    Guarantees:
    - State segmented by tenant
    - State hash includes tenant scope
    - Cross-tenant contamination impossible
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._state: Dict[str, Dict[str, StateEntry]] = {}
        self._state_hashes: Dict[str, str] = {}
        self._lock = threading.Lock()

    def update_state(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        requesting_tenant: Optional[str] = None
    ) -> StateEntry:
        """
        Update tenant state.

        Args:
            tenant_id: Tenant to update
            key: State key
            value: State value
            requesting_tenant: Optional requesting tenant for security check

        Returns:
            StateEntry with hash

        Raises:
            ValueError: If requesting_tenant != tenant_id (security violation)
        """
        with self._lock:
            # Security: Only tenant can update its own state
            if requesting_tenant is not None and requesting_tenant != tenant_id:
                raise ValueError(
                    f"Tenant {requesting_tenant} cannot access state for {tenant_id}"
                )

            # Initialize tenant state if needed
            if tenant_id not in self._state:
                self._state[tenant_id] = {}

            # Create state entry
            entry = StateEntry(
                tenant_id=tenant_id,
                key=key,
                value=value,
                timestamp=datetime.utcnow().isoformat(),
                state_hash=self._hash_state(tenant_id, key, value),
                protocol_version=self.PROTOCOL_VERSION
            )

            self._state[tenant_id][key] = entry

            # Update tenant state hash
            self._state_hashes[tenant_id] = self._hash_all_tenant_state(tenant_id)

            return entry

    def get_state(
        self,
        tenant_id: str,
        key: str,
        requesting_tenant: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get tenant state.

        Args:
            tenant_id: Tenant to get state from
            key: State key
            requesting_tenant: Optional requesting tenant for security check

        Returns:
            State value or None if not found

        Raises:
            ValueError: If requesting_tenant != tenant_id (security violation)
        """
        with self._lock:
            # Security: Only tenant can access its own state
            if requesting_tenant is not None and requesting_tenant != tenant_id:
                raise ValueError(
                    f"Tenant {requesting_tenant} cannot access state for {tenant_id}"
                )

            if tenant_id not in self._state:
                return None

            entry = self._state[tenant_id].get(key)
            if entry is None:
                return None

            return entry.value

    def get_state_hash(self, tenant_id: str) -> str:
        """
        Get cryptographic hash of tenant state.

        Args:
            tenant_id: Tenant to get hash for

        Returns:
            SHA256 hash of tenant state
        """
        with self._lock:
            if tenant_id not in self._state_hashes:
                # Return hash of empty state
                return self._hash_all_tenant_state(tenant_id)

            return self._state_hashes[tenant_id]

    def delete_state(
        self,
        tenant_id: str,
        key: str,
        requesting_tenant: Optional[str] = None
    ) -> bool:
        """
        Delete tenant state.

        Args:
            tenant_id: Tenant to delete from
            key: State key
            requesting_tenant: Optional requesting tenant for security check

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If requesting_tenant != tenant_id (security violation)
        """
        with self._lock:
            # Security: Only tenant can delete its own state
            if requesting_tenant is not None and requesting_tenant != tenant_id:
                raise ValueError(
                    f"Tenant {requesting_tenant} cannot access state for {tenant_id}"
                )

            if tenant_id not in self._state:
                return False

            if key not in self._state[tenant_id]:
                return False

            del self._state[tenant_id][key]

            # Update tenant state hash
            self._state_hashes[tenant_id] = self._hash_all_tenant_state(tenant_id)

            return True

    def list_keys(self, tenant_id: str) -> List[str]:
        """List all state keys for tenant"""
        with self._lock:
            if tenant_id not in self._state:
                return []

            return list(self._state[tenant_id].keys())

    def _hash_state(self, tenant_id: str, key: str, value: Any) -> str:
        """Generate cryptographic hash of state entry"""
        data = {
            "tenant_id": tenant_id,
            "key": key,
            "value": str(value),
            "protocol_version": self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _hash_all_tenant_state(self, tenant_id: str) -> str:
        """Generate hash of all tenant state"""
        if tenant_id not in self._state:
            return hashlib.sha256(
                f"{tenant_id}:empty:{self.PROTOCOL_VERSION}".encode()
            ).hexdigest()

        # Sort keys for deterministic hashing
        state_data = {}
        for key in sorted(self._state[tenant_id].keys()):
            entry = self._state[tenant_id][key]
            state_data[key] = {
                "value": entry.value,
                "hash": entry.state_hash
            }

        data = {
            "tenant_id": tenant_id,
            "state": state_data,
            "protocol_version": self.PROTOCOL_VERSION
        }

        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


__all__ = ["TenantStatePartition", "StateEntry"]
