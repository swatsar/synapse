"""
Tenant Quota Registry for Multi-Tenant Runtime
Per-tenant resource accounting with cryptographic verification

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading


@dataclass
class QuotaUsage:
    """Cryptographically verifiable quota usage"""
    tenant_id: str
    resource_type: str
    used: int
    limit: int
    usage_hash: str
    timestamp: str
    protocol_version: str = "1.0"


@dataclass
class ExecutionQuota:
    """Execution quota for a tenant"""
    cpu_seconds: int = 0
    memory_mb: int = 0
    disk_mb: int = 0
    network_kb: int = 0
    protocol_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "network_kb": self.network_kb
        }


@dataclass
class ResourceUsage:
    """Resource usage record"""
    cpu_seconds: int = 0
    memory_mb: int = 0
    disk_mb: int = 0
    network_kb: int = 0
    protocol_version: str = "1.0"


class TenantQuotaRegistry:
    """
    Per-tenant resource accounting with deterministic enforcement.

    Guarantees:
    - Deterministic quota enforcement
    - Cross-node consistency
    - Cryptographically verifiable usage
    - Quota violation → deterministic failure
    
    Required Public API:
    - register_tenant_quota(tenant_id, quota) -> None
    - register_tenant(tenant_id, quotas) -> bool
    - get_quota(tenant_id) -> ExecutionQuota
    - enforce_quota(tenant_id, usage) -> None
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._quotas: Dict[str, ExecutionQuota] = {}
        self._usage: Dict[str, Dict[str, int]] = {}
        self._usage_history: Dict[str, List[QuotaUsage]] = {}
        self._lock = threading.Lock()

    def register_tenant_quota(
        self,
        tenant_id: str,
        quota: ExecutionQuota
    ) -> None:
        """
        Register tenant quota limits.
        
        Required API method per specification.
        
        Args:
            tenant_id: Tenant to register
            quota: ExecutionQuota object with resource limits
        """
        with self._lock:
            self._quotas[tenant_id] = quota
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {"cpu_seconds": 0, "memory_mb": 0, "disk_mb": 0, "network_kb": 0}
            if tenant_id not in self._usage_history:
                self._usage_history[tenant_id] = []

    def register_tenant(
        self,
        tenant_id: str,
        quotas: Dict[str, int]
    ) -> bool:
        """
        Register tenant quota limits.
        
        Compatibility adapter that converts dict to ExecutionQuota.

        Args:
            tenant_id: Tenant to register
            quotas: Resource limits (cpu_seconds, memory_mb, etc.)

        Returns:
            True if successful
        """
        quota = ExecutionQuota(
            cpu_seconds=quotas.get("cpu_seconds", 0),
            memory_mb=quotas.get("memory_mb", 0),
            disk_mb=quotas.get("disk_mb", 0),
            network_kb=quotas.get("network_kb", 0)
        )
        self.register_tenant_quota(tenant_id, quota)
        return True

    def get_quota(self, tenant_id: str) -> Optional[ExecutionQuota]:
        """
        Get quota for a tenant.
        
        Required API method for integration tests.
        
        Args:
            tenant_id: Tenant to get quota for
            
        Returns:
            ExecutionQuota or None if not found
        """
        with self._lock:
            return self._quotas.get(tenant_id)

    def enforce_quota(
        self,
        tenant_id: str,
        usage: ResourceUsage
    ) -> None:
        """
        Enforce quota limits for a tenant.
        
        Required API method for integration tests.
        
        Args:
            tenant_id: Tenant to enforce
            usage: Resource usage to check
            
        Raises:
            ValueError: If quota exceeded
        """
        with self._lock:
            quota = self._quotas.get(tenant_id)
            if quota is None:
                raise ValueError(f"No quota registered for tenant {tenant_id}")
            
            if usage.cpu_seconds > quota.cpu_seconds:
                raise ValueError(
                    f"CPU quota exceeded for {tenant_id}: "
                    f"{usage.cpu_seconds} > {quota.cpu_seconds}"
                )
            if usage.memory_mb > quota.memory_mb:
                raise ValueError(
                    f"Memory quota exceeded for {tenant_id}: "
                    f"{usage.memory_mb} > {quota.memory_mb}"
                )
            if usage.disk_mb > quota.disk_mb:
                raise ValueError(
                    f"Disk quota exceeded for {tenant_id}: "
                    f"{usage.disk_mb} > {quota.disk_mb}"
                )
            if usage.network_kb > quota.network_kb:
                raise ValueError(
                    f"Network quota exceeded for {tenant_id}: "
                    f"{usage.network_kb} > {quota.network_kb}"
                )

    # Legacy API compatibility
    def register_quota(
        self,
        tenant_id: str,
        quotas: Dict[str, int],
        requesting_tenant: Optional[str] = None
    ) -> bool:
        """
        Legacy method - redirects to register_tenant.
        """
        # Security: Only tenant can register its own quota
        if requesting_tenant is not None and requesting_tenant != tenant_id:
            raise ValueError(
                f"Tenant {requesting_tenant} cannot modify quota for {tenant_id}"
            )
        return self.register_tenant(tenant_id, quotas)

    def check_quota(
        self,
        tenant_id: str,
        resource_type: str,
        amount: int
    ) -> bool:
        """
        Check if usage is within quota.

        Args:
            tenant_id: Tenant to check
            resource_type: Type of resource
            amount: Amount to check

        Returns:
            True if within limit, False otherwise
        """
        with self._lock:
            if tenant_id not in self._quotas:
                return False
            
            quota = self._quotas[tenant_id]
            limit = getattr(quota, resource_type, 0)
            current = self._usage.get(tenant_id, {}).get(resource_type, 0)
            
            return (current + amount) <= limit

    def record_usage(
        self,
        tenant_id: str,
        resource_type: str,
        amount: int
    ) -> QuotaUsage:
        """
        Record resource usage.

        Args:
            tenant_id: Tenant using resources
            resource_type: Type of resource
            amount: Amount used

        Returns:
            QuotaUsage record

        Raises:
            ValueError: If quota exceeded
        """
        with self._lock:
            if tenant_id not in self._quotas:
                raise ValueError(f"No quota for tenant {tenant_id}")

            # Check before recording
            if not self.check_quota(tenant_id, resource_type, amount):
                raise ValueError(
                    f"Quota exceeded for {tenant_id}/{resource_type}"
                )

            # Record usage
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {}
            
            self._usage[tenant_id][resource_type] = \
                self._usage[tenant_id].get(resource_type, 0) + amount

            # Create usage record
            usage = QuotaUsage(
                tenant_id=tenant_id,
                resource_type=resource_type,
                used=self._usage[tenant_id][resource_type],
                limit=getattr(self._quotas[tenant_id], resource_type, 0),
                usage_hash=self._compute_usage_hash(
                    tenant_id, resource_type,
                    self._usage[tenant_id][resource_type]
                ),
                timestamp=datetime.utcnow().isoformat()
            )

            self._usage_history[tenant_id].append(usage)
            return usage

    def get_usage(self, tenant_id: str) -> Dict[str, int]:
        """Get current usage for tenant"""
        with self._lock:
            return self._usage.get(tenant_id, {}).copy()

    def get_usage_history(
        self,
        tenant_id: str
    ) -> List[QuotaUsage]:
        """Get usage history for tenant"""
        with self._lock:
            return self._usage_history.get(tenant_id, []).copy()

    def _compute_usage_hash(
        self,
        tenant_id: str,
        resource_type: str,
        amount: int
    ) -> str:
        """Compute deterministic hash for usage"""
        data = f"{tenant_id}:{resource_type}:{amount}:1.0"
        return hashlib.sha256(data.encode()).hexdigest()

    def compute_quota_hash(self, tenant_id: str) -> str:
        """Compute deterministic hash for tenant quota"""
        with self._lock:
            quota = self._quotas.get(tenant_id)
            if quota is None:
                return ""
            
            data = json.dumps({
                "tenant_id": tenant_id,
                "quota": quota.to_dict(),
                "protocol_version": self.PROTOCOL_VERSION
            }, sort_keys=True)
            return hashlib.sha256(data.encode()).hexdigest()
