"""
Replay Manager for execution trace recording and replay
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC
import uuid

@dataclass
class ExecutionTrace:
    """Execution trace for replay"""
    trace_id: str
    workflow_id: str = "unknown"
    steps: List[Any] = field(default_factory=list)
    execution_time_ms: int = 0
    protocol_version: str = "1.0"

class ReplayManager:
    """Manager for recording and replaying execution traces"""
    
    def __init__(self):
        self._recordings: Dict[str, List[tuple]] = {}
        self._current_trace_id: Optional[str] = None
    
    def start_recording(self, trace_id: str):
        """Start recording a new trace"""
        self._current_trace_id = trace_id
        self._recordings[trace_id] = []
    
    def record(self, step_id: str, data: Dict[str, Any]):
        """Record a step execution"""
        if self._current_trace_id and self._current_trace_id in self._recordings:
            self._recordings[self._current_trace_id].append((step_id, data))
    
    def get_recording(self, trace_id: str) -> List[tuple]:
        """Get recorded trace"""
        return self._recordings.get(trace_id, [])
    
    def stop_recording(self):
        """Stop current recording"""
        self._current_trace_id = None
    
    def replay(self, trace_id: str) -> Optional[ExecutionTrace]:
        """Replay a recorded trace"""
        if trace_id not in self._recordings:
            return None
        
        return ExecutionTrace(
            trace_id=trace_id,
            steps=self._recordings[trace_id]
        )
