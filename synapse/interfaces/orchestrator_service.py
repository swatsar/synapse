"""
Orchestrator Service API
"""

from typing import Dict, Any, Optional
from datetime import datetime, UTC

from synapse.orchestrator.orchestrator_agent import OrchestratorAgent
from synapse.orchestrator.task_model import Task
from synapse.core.binding import BindingManager

class OrchestratorService:
    """Service API for orchestrator"""
    
    def __init__(self, binding_manager: Optional[BindingManager] = None):
        self.binding_manager = binding_manager or BindingManager()
        self.orchestrator = OrchestratorAgent(binding_manager=self.binding_manager)
    
    async def accept_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Accept and process a task"""
        agent_id = task_data.get("agent_id")
        capabilities = task_data.get("capabilities", task_data.get("required_capabilities", []))
        
        # Auto-bind capabilities to agent if specified
        if agent_id and capabilities:
            self.binding_manager.bind(agent_id, capabilities)
        
        task = Task(
            description=task_data.get("description", ""),
            agent_id=agent_id,
            required_capabilities=capabilities,
            capabilities=capabilities
        )
        
        result = await self.orchestrator.execute_task(task)
        
        return {
            "success": result.get("success", False),
            "task_id": task.id,
            "trace_id": result.get("trace_id"),
            "protocol_version": "1.0"
        }
    
    async def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get execution trace by ID"""
        return {
            "trace_id": trace_id,
            "steps": [],
            "protocol_version": "1.0"
        }
