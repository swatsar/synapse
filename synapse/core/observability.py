"""
Observability Core
"""

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC

@dataclass
class ExecutionEvent:
    """Execution event for traceability"""
    event_type: str
    data: Dict[str, Any]
    timestamp: str = ""
    protocol_version: str = "1.0"
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

class ObservabilityCore:
    """Core observability engine for events"""
    
    def __init__(self):
        self._subscribers: List[Callable] = []
        self._event_subscribers: Dict[str, List[Callable]] = {}
    
    async def subscribe(self, event_type_or_callback, callback: Optional[Callable] = None):
        """Subscribe to events - supports both subscribe(callback) and subscribe(event_type, callback)"""
        if callback is None:
            # subscribe(callback) - subscribe to all events
            self._subscribers.append(event_type_or_callback)
        else:
            # subscribe(event_type, callback) - subscribe to specific event
            if event_type_or_callback not in self._event_subscribers:
                self._event_subscribers[event_type_or_callback] = []
            self._event_subscribers[event_type_or_callback].append(callback)
        return self
    
    def unsubscribe(self, callback: Callable) -> 'ObservabilityCore':
        """Unsubscribe from events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
        for event_type in self._event_subscribers:
            if callback in self._event_subscribers[event_type]:
                self._event_subscribers[event_type].remove(callback)
        return self
    
    async def emit(self, event_type: str, data: Dict[str, Any]):
        """Publish event"""
        event = ExecutionEvent(event_type=event_type, data=data)
        
        # Notify all-event subscribers
        for callback in self._subscribers:
            if callable(callback):
                result = callback(event)
                if hasattr(result, '__await__'):
                    await result
        
        # Notify event-specific subscribers
        for callback in self._event_subscribers.get(event_type, []):
            if callable(callback):
                result = callback(event)
                if hasattr(result, '__await__'):
                    await result
        
        # Notify wildcard subscribers
        for callback in self._event_subscribers.get("*", []):
            if callable(callback):
                result = callback(event)
                if hasattr(result, '__await__'):
                    await result
    
    def publish(self, event: ExecutionEvent):
        """Publish event (synchronous wrapper)"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.emit(event.event_type, event.data))
        except RuntimeError:
            asyncio.run(self.emit(event.event_type, event.data))
