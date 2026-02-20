"""Connector Runtime - Event processing pipeline."""
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio

PROTOCOL_VERSION: str = "1.0"


@dataclass
class NormalizedEvent:
    """Normalized event from any connector source."""
    source: str
    message: str
    user_id: str
    timestamp: str
    raw: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: int = 0
    protocol_version: str = PROTOCOL_VERSION


class RateLimiter:
    """Simple rate limiter for connector events."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def check(self, user_id: str) -> bool:
        """Check if user is within rate limit."""
        import time
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


class ConnectorRuntime:
    """Runtime for processing connector events."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        orchestrator: Any = None,
        rate_limiter: Optional[RateLimiter] = None,
        capability_manager: Any = None,
        audit_logger: Any = None
    ):
        self.orchestrator = orchestrator
        self.rate_limiter = rate_limiter or RateLimiter()
        self.capability_manager = capability_manager
        self.audit_logger = audit_logger
        self._approval_check: Optional[Callable] = None
    
    def set_approval_required(self, check_fn: Callable):
        """Set function to check if approval is required."""
        self._approval_check = check_fn
    
    async def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming event through the pipeline."""
        # Rate limiting
        user_id = event.get("user_id", "unknown")
        if not self.rate_limiter.check(user_id):
            raise Exception(f"Rate limit exceeded for user {user_id}")
        
        # Capability check
        if self.capability_manager and event.get("required_capabilities"):
            for cap in event["required_capabilities"]:
                if not await self.capability_manager.check(cap):
                    raise Exception(f"Missing capability: {cap}")
        
        # Human approval check
        if self._approval_check and self._approval_check(event):
            return {"status": "pending_approval", "event": event}
        
        # Process through orchestrator
        if self.orchestrator:
            result = await self.orchestrator.handle(event)
            return result
        
        return {"status": "completed", "response": "processed"}
    
    def normalize_event(self, event: Dict[str, Any]) -> NormalizedEvent:
        """Normalize event from any source to standard format."""
        source = event.get("source", "unknown")
        
        if source == "telegram":
            return NormalizedEvent(
                source="telegram",
                message=event.get("text", ""),
                user_id=str(event.get("from", {}).get("id", "unknown")),
                timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                raw=event
            )
        elif source == "discord":
            return NormalizedEvent(
                source="discord",
                message=event.get("content", ""),
                user_id=str(event.get("author", {}).get("id", "unknown")),
                timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                raw=event
            )
        else:
            return NormalizedEvent(
                source=source,
                message=event.get("message", ""),
                user_id=event.get("user_id", "unknown"),
                timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                raw=event
            )
    
    def order_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Order events deterministically by timestamp."""
        return sorted(events, key=lambda e: e.get("timestamp", ""))
