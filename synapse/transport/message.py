"""
Transport Messages for orchestrator-node communication
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json

class CapabilityError(Exception):
    """Raised when capability check fails"""
    pass

@dataclass
class ExecutionTrace:
    """Execution trace"""
    trace_id: str
    workflow_id: str
    steps: List[Dict[str, Any]]
    execution_time_ms: int
    protocol_version: str = "1.0"
    
    def serialize(self) -> str:
        """Serialize trace to JSON"""
        return json.dumps({
            "trace_id": self.trace_id,
            "workflow_id": self.workflow_id,
            "steps": self.steps,
            "execution_time_ms": self.execution_time_ms,
            "protocol_version": self.protocol_version
        })
    
    @classmethod
    def deserialize(cls, data: str) -> "ExecutionTrace":
        """Deserialize trace from JSON"""
        parsed = json.loads(data)
        return cls(
            trace_id=parsed["trace_id"],
            workflow_id=parsed["workflow_id"], 
            steps=parsed["steps"],
            execution_time_ms=parsed["execution_time_ms"],
            protocol_version=parsed.get("protocol_version", "1.0")
        )

@dataclass
class ExecutionResult:
    """Execution result"""
    success: bool
    steps_executed: int = 0
    trace: Optional[ExecutionTrace] = None
    error: Optional[str] = None
    protocol_version: str = "1.0"
    
    def serialize(self) -> str:
        """Serialize result to JSON"""
        data = {
            "success": self.success,
            "steps_executed": self.steps_executed,
            "protocol_version": self.protocol_version
        }
        if self.trace:
            data["trace"] = self.trace.serialize()
        if self.error:
            data["error"] = self.error
        return json.dumps(data)
    
    @classmethod
    def deserialize(cls, data: str) -> "ExecutionResult":
        """Deserialize result from JSON"""
        parsed = json.loads(data)
        trace = None
        if "trace" in parsed:
            trace = ExecutionTrace.deserialize(parsed["trace"])
        return cls(
            success=parsed["success"],
            steps_executed=parsed.get("steps_executed", 0),
            trace=trace,
            error=parsed.get("error"),
            protocol_version=parsed.get("protocol_version", "1.0")
        )

@dataclass
class ExecutionRequest:
    """Execution request"""
    workflow: Any  # Should be WorkflowDefinition
    context: Any  # Should be SecureExecutionContext
    protocol_version: str = "1.0"
    
    def serialize(self) -> str:
        """Serialize request to JSON"""
        return json.dumps({
            "protocol_version": self.protocol_version
        })
    
    @classmethod
    def deserialize(cls, data: str) -> "ExecutionRequest":
        """Deserialize request from JSON"""
        parsed = json.loads(data)
        return cls(
            workflow=None,
            context=None,
            protocol_version=parsed.get("protocol_version", "1.0")
        )
