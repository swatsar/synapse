"""Capability Manager.

Manages capability tokens and access control.
"""
from typing import List, Optional, Set, Union
from fnmatch import fnmatch

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


class CapabilityError(Exception):
    """Exception raised when capability check fails.
    
    Attributes:
        required: Required capability that was denied
        message: Error message
    """
    
    def __init__(self, required: str = None, message: str = None):
        self.required = required
        self.message = message or f"Missing required capability: {required}"
        super().__init__(self.message)


class CapabilityCheckResult:
    """Result of capability check."""
    
    def __init__(self, approved: bool, granted: List[str], denied: List[str]):
        self.approved = approved
        self.granted = granted
        self.denied = denied
        self.blocked_capabilities = denied


class SecurityCheckResult:
    """Result of security check (alias for compatibility)."""
    
    def __init__(self, approved: bool, granted: List[str] = None, denied: List[str] = None):
        self.approved = approved
        self.granted = granted or []
        self.denied = denied or []
        self.blocked_capabilities = self.denied


class CapabilityManager:
    """Manages capability-based access control.
    
    Capabilities are tokens like:
    - fs:read:/workspace/**
    - fs:write:/workspace/project/*
    - net:http:*.example.com
    """
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._granted_capabilities: Set[str] = set()
    
    def grant(self, capability: str) -> None:
        """Grant a capability.
        
        Args:
            capability: Capability string to grant
        """
        self._granted_capabilities.add(capability)
        audit({
            "event": "capability_granted",
            "capability": capability
        })
    
    def grant_capability(self, capability: str) -> None:
        """Alias for grant() method for backward compatibility.
        
        Args:
            capability: Capability string to grant
        """
        self.grant(capability)
    
    def revoke(self, capability: str) -> None:
        """Revoke a capability.
        
        Args:
            capability: Capability string to revoke
        """
        self._granted_capabilities.discard(capability)
        audit({
            "event": "capability_revoked",
            "capability": capability
        })
    
    async def check_capability(
        self,
        context=None,
        required: Optional[Union[str, List[str]]] = None,
        capabilities: Optional[List[str]] = None
    ) -> Union[bool, SecurityCheckResult]:
        """Check if context has required capability.
        
        Supports multiple calling patterns:
        1. check_capability(["cap1", "cap2"]) -> bool (raises CapabilityError if missing)
        2. check_capability(context, required) -> bool
        3. check_capability(required=cap) -> SecurityCheckResult
        4. check_capability(capabilities=[...]) -> SecurityCheckResult
        
        Args:
            context: ExecutionContext with capabilities (optional)
            required: Required capability string or list (optional)
            capabilities: List of capabilities to check (optional)
            
        Returns:
            bool or SecurityCheckResult depending on call pattern
            
        Raises:
            CapabilityError: If capability check fails (for simple list pattern)
        """
        # Audit: capability check started
        audit(
            event="capability_check_started",
            required=str(required) if required else None,
            protocol_version=PROTOCOL_VERSION
        )

        # Pattern 1: List as first positional argument (simple test pattern)
        if isinstance(context, list):
            caps_to_check = context
            for cap in caps_to_check:
                # Use _has_capability for wildcard matching instead of exact match
                if not self._has_capability(cap):
                    # Audit: capability check failed
                    audit(
                        event="capability_check_failed",
                        missing_capability=cap,
                        protocol_version=PROTOCOL_VERSION
                    )

                    raise CapabilityError(f"Missing capability: {cap}")
            # Audit: capability check passed
            audit(
                event="capability_check_passed",
                capabilities=str(context) if context else "direct",
                protocol_version=PROTOCOL_VERSION
            )

            return True
        
        # Pattern 4: Direct capabilities list
        if capabilities:
            return self._check_capabilities_list(capabilities)
        
        # Pattern 3: Required without context
        if required and context is None:
            # Handle list of required capabilities
            if isinstance(required, list):
                for cap in required:
                    # Use _has_capability for wildcard matching
                    if not self._has_capability(cap):
                        # Audit: capability check failed
                        audit(
                            event="capability_check_failed",
                            missing_capability=cap,
                            protocol_version=PROTOCOL_VERSION
                        )

                        raise CapabilityError(f"Missing capability: {cap}")

                # Audit: capability check passed
                audit(
                    event="capability_check_passed",
                    capabilities=str(required),
                    protocol_version=PROTOCOL_VERSION
                )

                return True

            approved = self._has_capability(required) or "*" in self._granted_capabilities
            return SecurityCheckResult(
                approved=approved,
                granted=[required] if approved else [],
                denied=[] if approved else [required]
            )

        # Pattern 2: Context + required (original)
        if required and context is not None:
            return await self._check_single_capability(context, required)
        
        # Fallback: Check if context has any capabilities
        if context is not None:
            caps = getattr(context, "capabilities", [])
            return SecurityCheckResult(approved=len(caps) > 0, granted=caps, denied=[])
        
        # Default: approved
        return SecurityCheckResult(approved=True, granted=[], denied=[])
    
    def _has_capability(self, required: str) -> bool:
        """Check if a capability is granted (with wildcard matching).
        
        Args:
            required: Required capability
            
        Returns:
            True if granted
        """
        # Check for wildcard
        if "*" in self._granted_capabilities:
            return True
        
        # Check each granted capability against required
        for cap in self._granted_capabilities:
            if self._matches(cap, required):
                return True
        
        return False
    
    async def _check_single_capability(self, context, required: str) -> bool:
        """Check a single capability against context.
        
        Args:
            context: ExecutionContext
            required: Required capability
            
        Returns:
            True if granted
        """
        # Get capabilities from context
        capabilities = getattr(context, "capabilities", [])
        
        # Check for wildcard
        if "*" in capabilities:
            audit({
                "event": "capability_check",
                "required": required,
                "result": "granted",
                "reason": "wildcard"
            })
            return True
        
        # Check each granted capability against required
        for cap in capabilities:
            if self._matches(cap, required):
                audit({
                    "event": "capability_check",
                    "required": required,
                    "granted_by": cap,
                    "result": "granted"
                })
                return True
        
        # Check internal granted capabilities
        for cap in self._granted_capabilities:
            if self._matches(cap, required):
                audit({
                    "event": "capability_check",
                    "required": required,
                    "granted_by": cap,
                    "result": "granted"
                })
                return True
        
        audit({
            "event": "capability_check",
            "required": required,
            "result": "denied"
        })
        return False
    
    def _check_capabilities_list(self, capabilities: List[str]) -> SecurityCheckResult:
        """Check a list of capabilities.
        
        Args:
            capabilities: List of capabilities to check
            
        Returns:
            SecurityCheckResult
        """
        granted = []
        denied = []
        
        for cap in capabilities:
            if self._has_capability(cap) or "*" in self._granted_capabilities:
                granted.append(cap)
            else:
                denied.append(cap)
        
        return SecurityCheckResult(
            approved=len(denied) == 0,
            granted=granted,
            denied=denied
        )
    
    def _matches(self, pattern: str, value: str) -> bool:
        """Check if capability pattern matches value.
        
        Args:
            pattern: Capability pattern (may include wildcards)
            value: Value to check
            
        Returns:
            True if pattern matches
        """
        # Exact match
        if pattern == value:
            return True
        
        # Wildcard match using fnmatch
        if "*" in pattern:
            return fnmatch(value, pattern)
        
        # Prefix match for paths (e.g., fs:read:/ matches fs:read:/tmp/...)
        # This handles cases where pattern is a prefix of the value
        if value.startswith(pattern):
            return True
        
        # Special handling for path patterns ending with /**
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if value.startswith(prefix):
                return True
        
        # Special handling for path patterns ending with /
        # e.g., fs:read:/ matches fs:read:/tmp/...
        if pattern.endswith("/"):
            prefix = pattern[:-1]
            if value.startswith(prefix):
                return True
        
        return False
    
    def check_capabilities(self, context, required: List[str]) -> CapabilityCheckResult:
        """Check multiple capabilities.
        
        Args:
        # Audit: capabilities check started
        audit(
            event="capabilities_check_started",
            required_count=len(required) if required else 0,
            protocol_version=PROTOCOL_VERSION
        )
            context: ExecutionContext
            required: List of required capabilities
            
        Returns:
            CapabilityCheckResult
        """
        granted = []
        denied = []
        
        for cap in required:
            has_cap = self._sync_check(context, cap)
            
            if has_cap:
                granted.append(cap)
            else:
                denied.append(cap)
        
        return CapabilityCheckResult(
            approved=len(denied) == 0,
            granted=granted,
            denied=denied
        )
    
    def _sync_check(self, context, required: str) -> bool:
        """Synchronous capability check.
        
        Args:
            context: ExecutionContext
            required: Required capability
            
        Returns:
            True if granted
        """
        capabilities = getattr(context, "capabilities", [])
        
        if "*" in capabilities:
            return True
        
        for cap in capabilities:
            if self._matches(cap, required):
                return True
        
        for cap in self._granted_capabilities:
            if self._matches(cap, required):
                return True
        
        return False
    async def validate_capabilities(self, skill_name: str, required_capabilities: List[str]) -> bool:
        """Validate that all required capabilities are available.

        Args:
            skill_name: Name of the skill
            required_capabilities: List of required capabilities

        Returns:
            True if all capabilities are valid

        Raises:
            CapabilityError: If any capability is invalid
        """
        # Audit: capabilities validation started
        audit(
            event="capabilities_validation_started",
            skill_name=skill_name,
            capabilities_count=len(required_capabilities),
            protocol_version=PROTOCOL_VERSION
        )

        for cap in required_capabilities:
            if not self._is_valid_capability(cap):
                # Audit: capability check failed
                audit(
                    event="capability_check_failed",
                    missing_capability=cap,
                    protocol_version=PROTOCOL_VERSION
                )

                raise CapabilityError(f"Invalid capability: {cap}")

        # Audit: capabilities validation completed
        audit(
            event="capabilities_validation_completed",
            skill_name=skill_name,
            valid_count=len(required_capabilities),
            protocol_version=PROTOCOL_VERSION
        )

        return True

    def _is_valid_capability(self, capability: str) -> bool:
        """Check if a capability string is valid."""
        # Basic validation: capability should have format 'domain:action'
        if ':' not in capability:
            return False
        return True
