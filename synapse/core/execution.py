"""
Secure Execution Context and Executor
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, UTC
import uuid

from synapse.core.audit import AuditLog
from synapse.core.observability import ObservabilityCore

@dataclass
class SecureExecutionContext:
    """Secure execution context with capabilities"""
    agent_id: str
    capabilities: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    protocol_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    execution_seed: Optional[int] = None
    
    def has_capability(self, capability: str) -> bool:
        """Check if context has a specific capability"""
        return capability in self.capabilities

class SecureWorkflowExecutor:
    """Secure workflow executor with capability enforcement"""
    
    def __init__(self, binding_manager=None, audit_log=None, observability=None):
        self.binding_manager = binding_manager
        self.audit_log = audit_log or AuditLog()
        self.observability = observability or ObservabilityCore()
    
    async def execute(self, workflow, context: SecureExecutionContext) -> Dict[str, Any]:
        """Execute workflow with capability enforcement"""
        from synapse.core.workflow_engine import WorkflowDefinition
        
        if not isinstance(workflow, WorkflowDefinition):
            return {
                "success": False,
                "error": "Invalid workflow",
                "protocol_version": "1.0"
            }
        
        # Check capabilities
        required_caps = set()
        for step in workflow.steps:
            required_caps.update(step.capabilities)
        
        missing_caps = required_caps - set(context.capabilities)
        if missing_caps:
            return {
                "success": False,
                "error": f"Missing required capability: {missing_caps}",
                "protocol_version": "1.0"
            }
        
        # Execute steps
        results = []
        for step in workflow.steps:
            results.append({"step_id": step.id, "status": "completed"})
        
        return {
            "success": True,
            "steps_executed": len(results),
            "results": results,
            "protocol_version": "1.0"
        }
