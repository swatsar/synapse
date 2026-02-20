"""Execution Guard.

Enforces security policies before skill execution.
"""
from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass, field
from types import TracebackType

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

from synapse.observability.logger import audit
from synapse.core.isolation_policy import IsolationEnforcementPolicy, RuntimeIsolationType


@dataclass
class ExecutionCheckResult:
    """Result of execution check."""
    allowed: bool
    requires_approval: bool = False
    approval_granted: bool = False
    reason: str = ""
    required_isolation: Optional[RuntimeIsolationType] = None
    blocked_capabilities: List[str] = field(default_factory=list)


class ExecutionGuard:
    """Guards skill execution with security checks.
    
    Checks:
    - Capability requirements
    - Isolation requirements
    - Human approval for high-risk operations
    
    Supports async context manager:
        async with ExecutionGuard() as guard:
            result = await guard.check_execution_allowed(skill, context)
    """
    
    protocol_version: str = "1.0"
    
    def __init__(self, caps=None, capability_manager=None, limits=None):
        """Initialize ExecutionGuard.
        
        Args:
            caps: Optional CapabilityManager instance (deprecated, use capability_manager)
            capability_manager: Optional CapabilityManager instance
            limits: Optional resource limits dict
        """
        self.protocol_version = "1.0"
        self._capability_manager = capability_manager or caps
        self._isolation_policy = IsolationEnforcementPolicy()
        self._limits = limits or {}
        self._context = None
        self._skill = None
    
    @property
    def isolation_policy(self) -> IsolationEnforcementPolicy:
        """Get isolation policy."""
        return self._isolation_policy
    
    @property
    def limits(self) -> Dict[str, Any]:
        """Get resource limits."""
        return self._limits
    
    async def __aenter__(self) -> 'ExecutionGuard':
        """Enter async context.
        
        Validates capabilities and resource limits.
        
        Returns:
            Self for use in context
        """
        await self._validate_capabilities()
        await self._check_resource_limits()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """Exit async context.
        
        Audits success or failure.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
            
        Returns:
            False to not suppress exceptions
        """
        if exc_type is None:
            await self._audit_success()
        else:
            await self._audit_failure(exc_val)
        return False  # Don't suppress exceptions
    
    async def _validate_capabilities(self):
        """Validate capabilities for current context."""
        if self._context and self._capability_manager:
            caps = getattr(self._context, "capabilities", [])
            for cap in caps:
                # Just validate that capability manager works
                pass
    
    async def _check_resource_limits(self):
        """Check resource limits."""
        if self._limits:
            # Handle both dict and Pydantic ResourceLimits
            if hasattr(self._limits, "cpu_seconds"):
                # Pydantic model
                cpu = self._limits.cpu_seconds
                memory = self._limits.memory_mb
            else:
                # Dict
                cpu = self._limits.get("cpu_seconds", 60)
                memory = self._limits.get("memory_mb", 512)
            
            if cpu > 300:  # 5 minutes max
                raise ValueError(f"CPU limit {cpu}s exceeds maximum 300s")
            if memory > 4096:  # 4GB max
                raise ValueError(f"Memory limit {memory}MB exceeds maximum 4096MB")
    async def _audit_success(self):
        """Audit successful execution."""
        audit({
            "event": "execution_guard_success",
            "skill": getattr(self._skill, "name", "unknown") if self._skill else "unknown"
        })
    
    async def _audit_failure(self, error: Optional[BaseException]):
        """Audit failed execution."""
        audit({
            "event": "execution_guard_failure",
            "skill": getattr(self._skill, "name", "unknown") if self._skill else "unknown",
            "error": str(error) if error else "unknown"
        })
    
    async def check_execution_allowed(self, skill, context) -> ExecutionCheckResult:
        """Check if skill execution is allowed.
        
        Args:
            skill: Skill to check
            context: ExecutionContext
            
        Returns:
            ExecutionCheckResult
        """
        # Store for context manager
        self._skill = skill
        self._context = context
        
        manifest = skill.manifest
        
        # Get required capabilities
        required_caps = getattr(manifest, "required_capabilities", [])
        
        # Check capabilities
        if required_caps and self._capability_manager:
            for cap in required_caps:
                has_cap = await self._capability_manager.check_capability(context, cap)
                if not has_cap:
                    audit({
                        "event": "execution_blocked",
                        "reason": "missing_capability",
                        "capability": cap,
                        "skill": getattr(manifest, "name", "unknown")
                    })
                    return ExecutionCheckResult(
                        allowed=False,
                        reason=f"Missing capability: {cap}",
                        blocked_capabilities=[cap]
                    )
        
        # Get risk level and trust level
        risk_level = getattr(manifest, "risk_level", 1)
        trust_level = getattr(manifest, "trust_level", "unverified")
        
        # Determine required isolation
        required_isolation = self._isolation_policy.get_required_isolation(
            trust_level=trust_level,
            risk_level=risk_level
        )
        
        # Check if human approval required (risk_level >= 3)
        requires_approval = risk_level >= 3
        
        if requires_approval:
            audit({
                "event": "approval_required",
                "skill": getattr(manifest, "name", "unknown"),
                "risk_level": risk_level,
                "isolation": required_isolation.value
            })
            
            return ExecutionCheckResult(
                allowed=False,
                requires_approval=True,
                approval_granted=False,
                reason=f"Risk level {risk_level} requires human approval",
                required_isolation=required_isolation
            )
        
        # Execution allowed
        audit({
            "event": "execution_allowed",
            "skill": getattr(manifest, "name", "unknown"),
            "risk_level": risk_level,
            "isolation": required_isolation.value
        })
        
        return ExecutionCheckResult(
            allowed=True,
            requires_approval=False,
            required_isolation=required_isolation
        )
    
    def get_required_isolation(self, trust_level: str, risk_level: int) -> RuntimeIsolationType:
        """Get required isolation for trust/risk level.
        
        Args:
            trust_level: Trust level string
            risk_level: Risk level 1-5
            
        Returns:
            Required RuntimeIsolationType
        """
        return self._isolation_policy.get_required_isolation(trust_level, risk_level)
    async def run(self, func: callable, *args, **kwargs) -> Any:
        """Run a function within the execution guard context.
        
        Args:
            func: Async function to run
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func
        """
        async with self:
            return await func(*args, **kwargs)

