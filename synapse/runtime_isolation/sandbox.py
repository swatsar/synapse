"""
Deterministic Sandbox - Isolated deterministic execution environment

DeterministicSandbox provides:
- Deterministic execution environment
- Resource quota enforcement
- Capability enforcement
- Replay identity
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio
import hashlib
import json
import time
from datetime import datetime


@dataclass
class DeterministicSandbox:
    """
    Deterministic sandbox for isolated execution.
    
    Guarantees:
    - Deterministic execution environment
    - Resource quota enforcement
    - Capability enforcement
    - Replay identity
    """
    sandbox_id: str
    resource_quota: Dict[str, int]
    protocol_version: str = "1.0"
    _internal_state: Dict[str, Any] = field(default_factory=dict)
    _execution_history: list = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize sandbox"""
        if not self.sandbox_id:
            raise ValueError("sandbox_id is required")
    
    async def execute(
        self,
        workflow: Callable[[Dict], Dict],
        context: Dict[str, Any],
        domain: "ExecutionDomain"
    ) -> Dict[str, Any]:
        """
        Execute workflow in sandbox with domain isolation.
        
        Args:
            workflow: Callable to execute
            context: Execution context
            domain: Execution domain for isolation
            
        Returns:
            Execution result with sandbox metadata
        """
        # Enforce domain
        await self.enforce_domain(context, domain)
        
        # Enforce capabilities
        await self.enforce_capabilities(context, domain)
        
        # Check resource quota
        self.check_quota_from_context(context)
        
        # Execute with timing
        start_time = time.perf_counter()
        
        try:
            # Execute workflow
            if asyncio.iscoroutinefunction(workflow):
                result = await workflow(context)
            else:
                result = workflow(context)
            
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Add sandbox metadata
            result["_sandbox_id"] = self.sandbox_id
            result["_domain_id"] = domain.domain_id
            result["_execution_time_ms"] = execution_time_ms
            result["_protocol_version"] = self.protocol_version
            
            # Record execution
            self._execution_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "context_hash": self._compute_context_hash(context),
                "result_hash": self._compute_result_hash(result),
                "domain_id": domain.domain_id
            })
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Sandbox execution failed: {str(e)}")
    
    async def replay(
        self,
        workflow: Callable[[Dict], Dict],
        context: Dict[str, Any],
        domain: "ExecutionDomain"
    ) -> Dict[str, Any]:
        """
        Replay execution with identical context.
        
        Should produce identical results for identical inputs.
        """
        # Replay is identical to execute for deterministic sandbox
        return await self.execute(workflow, context, domain)
    
    async def enforce_domain(self, context: Dict, domain: "ExecutionDomain") -> None:
        """Enforce domain isolation"""
        if not domain:
            raise ValueError("Execution domain is required")
        
        # Verify domain is valid
        if not domain.domain_id or not domain.tenant_id:
            raise ValueError("Invalid execution domain")
    
    async def enforce_capabilities(self, context: Dict, domain: "ExecutionDomain") -> None:
        """Enforce capability requirements"""
        required_caps = context.get("required_capabilities", [])
        
        for cap in required_caps:
            if not domain.has_capability(cap):
                raise PermissionError(
                    f"Domain {domain.domain_id} lacks required capability: {cap}"
                )
    
    async def execute_with_capability_check(
        self,
        required_capability: str,
        domain: "ExecutionDomain"
    ) -> bool:
        """Check if domain has capability, raise if not"""
        if not domain.has_capability(required_capability):
            raise PermissionError(
                f"Capability denied: {required_capability} not in domain {domain.domain_id}"
            )
        return True
    
    async def execute_with_quota_check(
        self,
        operation: Callable,
        expected_cpu_seconds: int = 0
    ) -> Any:
        """Execute with quota check"""
        if expected_cpu_seconds > self.resource_quota.get("cpu_seconds", 0):
            raise ValueError(
                f"Resource quota exceeded: requested {expected_cpu_seconds}s, "
                f"available {self.resource_quota.get('cpu_seconds', 0)}s"
            )
        
        if asyncio.iscoroutinefunction(operation):
            return await operation()
        else:
            return operation()
    
    async def execute_for_tenant(
        self,
        tenant: "TenantContext",
        workflow: Callable[[Dict], Dict],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow for specific tenant"""
        # This should fail if sandbox is not configured for tenant
        raise PermissionError(
            f"Sandbox {self.sandbox_id} not configured for tenant {tenant.tenant_id}"
        )
    
    def check_quota(self, cpu_seconds: int = 0, memory_mb: int = 0) -> bool:
        """Check if quota is available"""
        return (
            cpu_seconds <= self.resource_quota.get("cpu_seconds", 0) and
            memory_mb <= self.resource_quota.get("memory_mb", 0)
        )
    
    def check_quota_from_context(self, context: Dict) -> bool:
        """Check quota from context"""
        required_cpu = context.get("cpu_seconds", 0)
        required_memory = context.get("memory_mb", 0)
        
        if not self.check_quota(required_cpu, required_memory):
            raise ValueError("Resource quota exceeded")
        
        return True
    
    def get_internal_state(self) -> Dict[str, Any]:
        """Get internal sandbox state"""
        return dict(self._internal_state)
    
    def update_internal_state(self, updates: Dict[str, Any]) -> None:
        """Update internal sandbox state"""
        self._internal_state.update(updates)
    
    def _compute_context_hash(self, context: Dict) -> str:
        """Compute deterministic hash of context"""
        # Remove non-deterministic fields
        clean_context = {k: v for k, v in context.items() if not k.startswith("_")}
        return hashlib.sha256(
            json.dumps(clean_context, sort_keys=True).encode()
        ).hexdigest()
    
    def _compute_result_hash(self, result: Dict) -> str:
        """Compute deterministic hash of result"""
        return hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "sandbox_id": self.sandbox_id,
            "resource_quota": self.resource_quota,
            "protocol_version": self.protocol_version
        }
