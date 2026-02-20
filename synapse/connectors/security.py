"""Connector Security - Rate limiting and security utilities."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time

PROTOCOL_VERSION: str = "1.0"


class RateLimiter:
    """Rate limiter for connector events."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def check(self, user_id: str) -> bool:
        """Check if user is within rate limit."""
        now = time.time()
        
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        # Clean old requests
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if now - t < self.window_seconds
        ]
        
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        
        self._requests[user_id].append(now)
        return True


@dataclass
class SecurityContext:
    """Security context for connector operations."""
    user_id: str
    source: str
    capabilities: List[str] = field(default_factory=list)
    rate_limit_remaining: int = 100
    is_authenticated: bool = False
    protocol_version: str = PROTOCOL_VERSION


class ConnectorSecurity:
    """Security layer for connectors."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self):
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._capability_cache: Dict[str, List[str]] = {}
    
    def get_rate_limiter(self, source: str, max_requests: int = 100, window_seconds: int = 60) -> RateLimiter:
        """Get or create rate limiter for source."""
        if source not in self._rate_limiters:
            self._rate_limiters[source] = RateLimiter(max_requests, window_seconds)
        return self._rate_limiters[source]
    
    def validate_event(self, event: dict) -> bool:
        """Validate event structure."""
        required_fields = ["source", "message"]
        return all(field in event for field in required_fields)
    
    def check_capability(self, user_id: str, capability: str) -> bool:
        """Check if user has capability."""
        user_caps = self._capability_cache.get(user_id, [])
        return capability in user_caps
    
    def grant_capability(self, user_id: str, capability: str) -> None:
        """Grant capability to user."""
        if user_id not in self._capability_cache:
            self._capability_cache[user_id] = []
        if capability not in self._capability_cache[user_id]:
            self._capability_cache[user_id].append(capability)
    
    def revoke_capability(self, user_id: str, capability: str) -> None:
        """Revoke capability from user."""
        if user_id in self._capability_cache:
            if capability in self._capability_cache[user_id]:
                self._capability_cache[user_id].remove(capability)
