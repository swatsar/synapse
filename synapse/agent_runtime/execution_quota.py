"""
Execution Quota - Resource Limits for Agent Execution
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime, UTC
import time


@dataclass
class QuotaLimits:
    """Execution quota limits"""
    max_steps: int = 10
    max_time_ms: int = 30000
    max_capability_calls: int = 100
    protocol_version: str = "1.0"


@dataclass
class QuotaState:
    """Current quota state"""
    steps_used: int = 0
    time_used_ms: int = 0
    capability_calls_used: int = 0
    start_time: Optional[float] = None
    protocol_version: str = "1.0"


class ExecutionQuota:
    """Manages execution quotas for agents"""
    
    def __init__(self, limits: QuotaLimits):
        self.limits = limits
        self.state = QuotaState()
        self._violations: list = []
    
    def start(self):
        """Start quota tracking"""
        self.state = QuotaState(start_time=time.perf_counter())
        self._violations = []
    
    def record_step(self) -> bool:
        """Record a step execution, returns False if quota exceeded"""
        self.state.steps_used += 1
        
        if self.state.steps_used > self.limits.max_steps:
            self._violations.append("max_steps_exceeded")
            return False
        return True
    
    def record_capability_call(self) -> bool:
        """Record a capability call, returns False if quota exceeded"""
        self.state.capability_calls_used += 1
        
        if self.state.capability_calls_used > self.limits.max_capability_calls:
            self._violations.append("max_capability_calls_exceeded")
            return False
        return True
    
    def check_time(self) -> bool:
        """Check if time quota exceeded"""
        if self.state.start_time is None:
            return True
        
        elapsed_ms = int((time.perf_counter() - self.state.start_time) * 1000)
        self.state.time_used_ms = elapsed_ms
        
        if elapsed_ms > self.limits.max_time_ms:
            self._violations.append("max_time_exceeded")
            return False
        return True
    
    def is_within_limits(self) -> bool:
        """Check if all quotas are within limits"""
        return (
            self.state.steps_used <= self.limits.max_steps and
            self.state.time_used_ms <= self.limits.max_time_ms and
            self.state.capability_calls_used <= self.limits.max_capability_calls
        )
    
    def get_violations(self) -> list:
        """Get list of quota violations"""
        return list(self._violations)
    
    def get_remaining_steps(self) -> int:
        """Get remaining steps"""
        return max(0, self.limits.max_steps - self.state.steps_used)
    
    def get_remaining_time_ms(self) -> int:
        """Get remaining time in ms"""
        return max(0, self.limits.max_time_ms - self.state.time_used_ms)
    
    def get_remaining_capability_calls(self) -> int:
        """Get remaining capability calls"""
        return max(0, self.limits.max_capability_calls - self.state.capability_calls_used)
    
    def get_state_hash(self) -> str:
        """Get deterministic hash of quota state"""
        import hashlib
        import json
        
        data = {
            "steps_used": self.state.steps_used,
            "time_used_ms": self.state.time_used_ms,
            "capability_calls_used": self.state.capability_calls_used,
            "violations": sorted(self._violations)
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
