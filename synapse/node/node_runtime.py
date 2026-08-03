PROTOCOL_VERSION: str = "1.0"
"""
Local Execution Node Runtime
"""

import time

from synapse.core.execution import SecureExecutionContext, SecureWorkflowExecutor
from synapse.core.workflow_engine import WorkflowDefinition
from synapse.node.node_security import NodeSecurity
from synapse.transport.message import (
    ExecutionResult,
    ExecutionTrace,
)


class ExecutionNode:
    """Local execution node"""
    
    def __init__(self, executor: SecureWorkflowExecutor, security: NodeSecurity):
        self.executor = executor
        self.security = security
        self._trace_counter = 0
    
    async def execute_workflow(self, workflow: WorkflowDefinition, context: SecureExecutionContext):
        """Execute workflow with security validation"""
        # Validate capabilities - re-raise CapabilityError for proper security enforcement
        self.security.check_required_capabilities(workflow, context)
        self.security.validate_capabilities(context)
        
        # Execute workflow
        start_time = time.time()
        try:
            await self.executor.execute(workflow, context)
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))
        
        execution_time = time.time() - start_time
        
        # Create trace
        self._trace_counter += 1
        trace = ExecutionTrace(
            trace_id=f"trace_{self._trace_counter:08d}",
            workflow_id=getattr(workflow, "id", "unknown"),
            steps=[],
            execution_time_ms=int(execution_time * 1000)
        )
        
        return ExecutionResult(success=True, steps_executed=len(trace.steps), trace=trace)
