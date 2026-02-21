"""
Isolation Enforcer - Runtime isolation enforcement

IsolationEnforcer provides:
- Tenant isolation enforcement
- Domain boundary enforcement
- Cross-tenant execution prevention
- Replay identity verification
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import hashlib
import json


@dataclass
class IsolationEnforcer:
    """
    Enforces runtime isolation between tenants and domains.
    
    Security Invariants:
    - Tenant isolation
    - Domain capability boundary
    - Deterministic sandbox
    - No cross-tenant execution
    - Replay identical per domain
    """
    protocol_version: str = "1.0"
    _enforcement_log: list = field(default_factory=list)
    
    async def enforce_tenant_isolation(
        self,
        tenant: "TenantContext",
        domain: "ExecutionDomain"
    ) -> bool:
        """
        Enforce tenant isolation.
        
        Tenant can only execute in their own domain.
        """
        if tenant.tenant_id != domain.tenant_id:
            raise PermissionError(
                f"Tenant isolation violation: tenant {tenant.tenant_id} "
                f"cannot execute in domain {domain.domain_id} "
                f"(belongs to tenant {domain.tenant_id})"
            )
        
        self._log_enforcement("tenant_isolation", tenant.tenant_id, domain.domain_id, True)
        return True
    
    async def enforce_domain_boundary(
        self,
        capability_domain: "CapabilityDomain",
        capability: str
    ) -> bool:
        """
        Enforce domain capability boundary.
        
        Capability must be within domain scope.
        """
        result = capability_domain.validate_capability_scope(capability)
        
        if not result:
            self._log_enforcement(
                "domain_boundary",
                capability_domain.domain_id,
                capability,
                False
            )
        
        return result
    
    async def prevent_cross_tenant_execution(
        self,
        tenant_a: "TenantContext",
        tenant_b: "TenantContext"
    ) -> bool:
        """
        Prevent cross-tenant execution.
        
        Different tenants cannot execute in each other's context.
        """
        if tenant_a.tenant_id != tenant_b.tenant_id:
            raise PermissionError(
                f"Cross-tenant execution blocked: "
                f"{tenant_a.tenant_id} cannot execute as {tenant_b.tenant_id}"
            )
        
        return True
    
    async def enforce_cross_domain_isolation(
        self,
        domain_a: "ExecutionDomain",
        domain_b: "ExecutionDomain"
    ) -> bool:
        """
        Enforce isolation between different domains.
        """
        if domain_a.domain_id != domain_b.domain_id:
            raise PermissionError(
                f"Cross-domain execution blocked: "
                f"{domain_a.domain_id} cannot access {domain_b.domain_id}"
            )
        
        return True
    
    async def verify_replay_identity(
        self,
        domain: "ExecutionDomain",
        execution_result: Dict[str, Any],
        replay_result: Dict[str, Any]
    ) -> bool:
        """
        Verify that replay produces identical results.
        """
        # Compute hashes of results (excluding metadata)
        exec_hash = self._compute_result_hash(execution_result)
        replay_hash = self._compute_result_hash(replay_result)
        
        if exec_hash != replay_hash:
            raise ValueError(
                f"Replay identity violation in domain {domain.domain_id}: "
                f"execution hash {exec_hash} != replay hash {replay_hash}"
            )
        
        self._log_enforcement(
            "replay_identity",
            domain.domain_id,
            exec_hash,
            True
        )
        
        return True
    
    async def validate_cross_tenant_capability(
        self,
        tenant: "TenantContext",
        capability: str
    ) -> bool:
        """
        Validate that tenant cannot use another tenant's capability.
        """
        # Check if capability belongs to tenant
        if not tenant.has_capability(capability):
            raise PermissionError(
                f"Tenant {tenant.tenant_id} cannot use capability {capability}"
            )
        
        return True
    
    async def enforce_capability_escalation_prevention(
        self,
        capability_domain: "CapabilityDomain",
        current_cap: str,
        target_cap: str
    ) -> bool:
        """
        Prevent capability escalation.
        """
        if not capability_domain.can_escalate_to(target_cap):
            raise PermissionError(
                f"Capability escalation blocked: "
                f"cannot escalate from {current_cap} to {target_cap}"
            )
        
        return True
    
    def _log_enforcement(
        self,
        enforcement_type: str,
        source: str,
        target: str,
        allowed: bool
    ) -> None:
        """Log enforcement action"""
        from datetime import datetime
        
        self._enforcement_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": enforcement_type,
            "source": source,
            "target": target,
            "allowed": allowed,
            "protocol_version": self.protocol_version
        })
    
    def _compute_result_hash(self, result: Dict[str, Any]) -> str:
        """Compute deterministic hash of result"""
        # Remove non-deterministic metadata
        clean_result = {
            k: v for k, v in result.items()
            if not k.startswith("_")
        }
        return hashlib.sha256(
            json.dumps(clean_result, sort_keys=True).encode()
        ).hexdigest()
    
    def get_enforcement_log(self) -> list:
        """Get enforcement log"""
        return list(self._enforcement_log)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "protocol_version": self.protocol_version,
            "enforcement_count": len(self._enforcement_log)
        }
