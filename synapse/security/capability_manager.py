"""Capability Manager.

Manages capability tokens and access control with path traversal protection.
"""
from pathlib import PurePath
from typing import List, Optional, Set, Union
from fnmatch import fnmatch

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

from synapse.observability.logger import audit


class CapabilityError(Exception):
    """Exception raised when capability check fails."""
    
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
    """Manages capability-based access control with path traversal protection."""
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._granted_capabilities: Set[str] = set()
    
    def grant(self, capability: str) -> None:
        """Grant a capability."""
        self._granted_capabilities.add(capability)
        audit({"event": "capability_granted", "capability": capability})
    
    def grant_capability(self, capability: str) -> None:
        """Alias for grant() method."""
        self.grant(capability)
    
    def revoke(self, capability: str) -> None:
        """Revoke a capability."""
        self._granted_capabilities.discard(capability)
        audit({"event": "capability_revoked", "capability": capability})
    
    async def check_capability(self, context=None, required=None, capabilities=None):
        """Check if context has required capability."""
        audit(event="capability_check_started", required=str(required) if required else None, protocol_version=PROTOCOL_VERSION)
        
        if isinstance(context, list):
            for cap in context:
                if not self._has_capability(cap):
                    audit(event="capability_check_failed", missing_capability=cap, protocol_version=PROTOCOL_VERSION)
                    raise CapabilityError(f"Missing capability: {cap}")
            audit(event="capability_check_passed", capabilities=str(context), protocol_version=PROTOCOL_VERSION)
            return True
        
        if capabilities:
            return self._check_capabilities_list(capabilities)
        
        if required and context is None:
            if isinstance(required, list):
                for cap in required:
                    if not self._has_capability(cap):
                        audit(event="capability_check_failed", missing_capability=cap, protocol_version=PROTOCOL_VERSION)
                        raise CapabilityError(f"Missing capability: {cap}")
                audit(event="capability_check_passed", capabilities=str(required), protocol_version=PROTOCOL_VERSION)
                return True
            
            approved = self._has_capability(required) or "*" in self._granted_capabilities
            return SecurityCheckResult(approved=approved, granted=[required] if approved else [], denied=[] if approved else [required])
        
        if required and context is not None:
            return await self._check_single_capability(context, required)
        
        if context is not None:
            caps = getattr(context, "capabilities", [])
            return SecurityCheckResult(approved=len(caps) > 0, granted=caps, denied=[])
        
        return SecurityCheckResult(approved=True, granted=[], denied=[])
    
    def _has_capability(self, required: str) -> bool:
        """Check if a capability is granted."""
        if "*" in self._granted_capabilities:
            return True
        for cap in self._granted_capabilities:
            if self._matches(cap, required):
                return True
        return False
    
    async def _check_single_capability(self, context, required: str) -> bool:
        """Check a single capability against context."""
        capabilities = getattr(context, "capabilities", [])
        
        if "*" in capabilities:
            audit({"event": "capability_check", "required": required, "result": "granted", "reason": "wildcard"})
            return True
        
        for cap in capabilities:
            if self._matches(cap, required):
                audit({"event": "capability_check", "required": required, "granted_by": cap, "result": "granted"})
                return True
        
        for cap in self._granted_capabilities:
            if self._matches(cap, required):
                audit({"event": "capability_check", "required": required, "granted_by": cap, "result": "granted"})
                return True
        
        audit({"event": "capability_check", "required": required, "result": "denied"})
        return False
    
    def _check_capabilities_list(self, capabilities: List[str]) -> SecurityCheckResult:
        """Check a list of capabilities."""
        granted = []
        denied = []
        for cap in capabilities:
            if self._has_capability(cap) or "*" in self._granted_capabilities:
                granted.append(cap)
            else:
                denied.append(cap)
        return SecurityCheckResult(approved=len(denied) == 0, granted=granted, denied=denied)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize a path to prevent traversal attacks."""
        if not path:
            return ""
        try:
            return str(PurePath(path).resolve())
        except Exception:
            raise ValueError(f"Invalid path: {path}")
    
    def _is_path_traversal_attempt(self, path: str) -> bool:
        """Check if a path contains traversal patterns."""
        traversal_patterns = ["..", "%2e%2e", "%252e", "..%2f", "%2e%2e%2f"]
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in traversal_patterns)
    
    def _is_path_capability(self, capability: str) -> bool:
        """Check if a capability string is path-based."""
        return any(capability.startswith(prefix) for prefix in ["fs:", "file:", "path:"])
    
    def _validate_path_boundary(self, pattern: str, value: str) -> bool:
        """Validate that a value stays within pattern boundaries."""
        parts = pattern.split(":", 2)
        if len(parts) < 3:
            return True
        pattern_path = parts[2]
        if pattern_path.endswith("/**"):
            prefix = pattern_path[:-3]
            if not value.startswith(prefix):
                return False
        return True
    
    def _safe_wildcard_match(self, pattern: str, value: str) -> bool:
        """Safely match wildcards on normalized paths."""
        import re
        regex = pattern.replace("**", "__DBL__").replace("*", "[^/]*").replace("__DBL__", ".*")
        try:
            return bool(re.match(f"^{regex}$", value))
        except re.error:
            return fnmatch(value, pattern)
    
    def _matches(self, pattern: str, value: str) -> bool:
        """Check if capability pattern matches value with path traversal protection."""
        # SECURITY: Check for path traversal attempts
        if self._is_path_traversal_attempt(value):
            audit({"event": "path_traversal_detected", "value": value, "protocol_version": PROTOCOL_VERSION})
            raise ValueError(f"Path traversal attempt detected: {value}")
        if self._is_path_traversal_attempt(pattern):
            audit({"event": "path_traversal_detected", "pattern": pattern, "protocol_version": PROTOCOL_VERSION})
            raise ValueError(f"Path traversal attempt in pattern: {pattern}")
        
        # Normalize paths
        try:
            normalized_pattern = self._normalize_path(pattern)
            normalized_value = self._normalize_path(value)
        except ValueError:
            return False
        
        # Exact match
        if normalized_pattern == normalized_value:
            return True
        
        # Wildcard match with boundary validation
        if "*" in pattern:
            if self._is_path_capability(pattern):
                if not self._validate_path_boundary(normalized_pattern, normalized_value):
                    audit({"event": "path_boundary_violation", "pattern": normalized_pattern, "value": normalized_value, "protocol_version": PROTOCOL_VERSION})
                    return False
                return self._safe_wildcard_match(normalized_pattern, normalized_value)
        
        # Prefix match
        if normalized_value.startswith(normalized_pattern):
            return True
        
        return False
    
    def check_capabilities(self, context, required: List[str]) -> CapabilityCheckResult:
        """Check multiple capabilities."""
        audit(event="capabilities_check_started", required_count=len(required) if required else 0, protocol_version=PROTOCOL_VERSION)
        granted = []
        denied = []
        for cap in required:
            has_cap = self._sync_check(context, cap)
            if has_cap:
                granted.append(cap)
            else:
                denied.append(cap)
        return CapabilityCheckResult(approved=len(denied) == 0, granted=granted, denied=denied)
    
    def _sync_check(self, context, required: str) -> bool:
        """Synchronous capability check."""
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
        """Validate that all required capabilities are available."""
        audit(event="capabilities_validation_started", skill_name=skill_name, capabilities_count=len(required_capabilities), protocol_version=PROTOCOL_VERSION)
        for cap in required_capabilities:
            if not self._is_valid_capability(cap):
                audit(event="capability_check_failed", missing_capability=cap, protocol_version=PROTOCOL_VERSION)
                raise CapabilityError(f"Invalid capability: {cap}")
        audit(event="capabilities_validation_completed", skill_name=skill_name, valid_count=len(required_capabilities), protocol_version=PROTOCOL_VERSION)
        return True
    
    def _is_valid_capability(self, capability: str) -> bool:
        """Check if a capability string is valid."""
        if ":" not in capability:
            return False
        if self._is_path_traversal_attempt(capability):
            return False
        return True
