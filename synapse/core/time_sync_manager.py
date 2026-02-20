"""Time Synchronization Manager.

Provides authoritative core time normalization for distributed execution.
"""
from datetime import datetime, timezone, timedelta
from typing import Union, Optional, Dict

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Global offset for class-level operations
_global_offset_ms: float = 0.0


class TimeSyncManager:
    """Manages time synchronization across distributed nodes.
    
    Core is the authoritative time source.
    Nodes send offset in heartbeat.
    Core normalizes timestamps.
    """
    
    protocol_version: str = "1.0"
    _global_offset_ms: float = 0.0
    _node_offsets: Dict[str, float] = {}  # Per-node offsets at class level
    _last_timestamp: Optional[float] = None
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._node_offsets_instance: dict = {}
    
    @classmethod
    def set_offset(cls, offset_ms: float, node_id: Optional[str] = None) -> None:
        """Set time offset for testing.
        
        Args:
            offset_ms: Offset in milliseconds
            node_id: Optional node ID for per-node offset
        """
        if node_id is not None:
            cls._node_offsets[node_id] = offset_ms
        else:
            cls._global_offset_ms = offset_ms
    
    @classmethod
    def now(cls, node_id: Optional[str] = None) -> datetime:
        """Get current normalized time.
        
        Args:
            node_id: Optional node ID for per-node offset
            
        Returns:
            Current UTC datetime with offset applied
        """
        base_time = datetime.now(timezone.utc)
        
        # Apply per-node offset if available
        if node_id is not None and node_id in cls._node_offsets:
            offset = cls._node_offsets[node_id]
        else:
            offset = cls._global_offset_ms
        
        # Apply offset as timedelta
        return base_time - timedelta(milliseconds=offset)
    
    @classmethod
    def normalize(cls, timestamp: Union[datetime, float], offset_ms: float = 0) -> float:
        """Normalize timestamp to UTC float.
        
        Args:
            timestamp: datetime or float timestamp
            offset_ms: Optional offset in milliseconds
            
        Returns:
            Normalized float timestamp
        """
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            result = timestamp.timestamp()
        else:
            result = float(timestamp)
        
        # Apply offset if provided
        if offset_ms:
            result = result - (offset_ms / 1000.0)
        
        return result
    
    def register_node_offset(self, node_id: str, offset_ms: float) -> None:
        """Register time offset for a node.
        
        Args:
            node_id: Node identifier
            offset_ms: Offset in milliseconds
        """
        self._node_offsets_instance[node_id] = offset_ms
        # Also update class-level
        TimeSyncManager._node_offsets[node_id] = offset_ms
    
    def get_normalized_time(self, node_id: str, local_time: float) -> float:
        """Get normalized time for a node.
        
        Args:
            node_id: Node identifier
            local_time: Local timestamp from node
            
        Returns:
            Normalized timestamp
        """
        offset = self._node_offsets_instance.get(node_id, 0)
        return local_time - (offset / 1000.0)
