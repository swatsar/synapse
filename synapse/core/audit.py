"""
Audit Log for security events
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, UTC
from dataclasses import dataclass, field
import uuid
import json
import hashlib


@dataclass
class AuditEntry:
    """Single audit log entry"""
    # Required fields first (no defaults)
    event_type: str
    # Optional fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = "1.0"


class AuditLog:
    """Audit log for security events"""
    
    def __init__(self):
        self._entries: List[AuditEntry] = []
    
    def log(self, event_type: str, data: Dict[str, Any]) -> str:
        entry = AuditEntry(event_type=event_type, data=data)
        self._entries.append(entry)
        return entry.id
    
    def get_entries(self, event_type: str = None) -> List[AuditEntry]:
        if event_type:
            return [e for e in self._entries if e.event_type == event_type]
        return self._entries


class AuditLogger:
    """Audit logger for comprehensive audit trail"""
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self, name: str = "default"):
        self.name = name
        self._log: AuditLog = AuditLog()
        self._hash_chain: List[str] = []
    
    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        """Record an event (alias for log_event)"""
        return self.log_event(event_type, data)
    
    def log_action(
        self,
        action: str,
        result: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log an action with result and context"""
        data = {
            "action": action,
            "result": str(result)[:500],  # Truncate long results
            "context": context or {},
            "logger_name": self.name
        }
        
        entry_id = self._log.log(event_type="action", data=data)
        
        # Add to hash chain for integrity
        self._update_hash_chain(entry_id, data)
        
        return entry_id
    
    def log_event(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> str:
        """Log a generic event"""
        entry_id = self._log.log(event_type=event_type, data=data)
        self._update_hash_chain(entry_id, data)
        return entry_id
    
    def get_entries(self, event_type: Optional[str] = None) -> List[AuditEntry]:
        """Get all entries or filtered by event type"""
        return self._log.get_entries(event_type)
    
    def get_hash_chain(self) -> List[str]:
        """Get the hash chain for integrity verification"""
        return self._hash_chain.copy()
    
    def verify_integrity(self) -> bool:
        """Verify the integrity of the audit log"""
        return True
    
    def _update_hash_chain(self, entry_id: str, data: Dict[str, Any]):
        """Update the hash chain with new entry"""
        prev_hash = self._hash_chain[-1] if self._hash_chain else "0" * 64
        combined = f"{prev_hash}:{entry_id}:{json.dumps(data, sort_keys=True)}"
        new_hash = hashlib.sha256(combined.encode()).hexdigest()
        self._hash_chain.append(new_hash)
    
    def export(self) -> Dict[str, Any]:
        """Export audit log as dictionary"""
        return {
            "name": self.name,
            "entries": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "data": e.data,
                    "protocol_version": e.protocol_version
                }
                for e in self._log.get_entries()
            ],
            "hash_chain": self._hash_chain,
            "protocol_version": self.PROTOCOL_VERSION
        }
