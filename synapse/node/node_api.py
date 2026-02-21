"""
Node API for external communication
"""

from synapse.node.node_runtime import ExecutionNode
from synapse.transport.message import ExecutionRequest, ExecutionResult

class NodeAPI:
    """API interface for execution node"""
    
    def __init__(self, node: ExecutionNode):
        self.node = node
    
    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute workflow request"""
        try:
            return await self.node.execute_workflow(request.workflow, request.context)
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))
