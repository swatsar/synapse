"""
Orchestrator Agent for task execution
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
from datetime import datetime

# Local imports
from synapse.orchestrator.task_model import Task
from synapse.orchestrator.planning import TaskPlanner
from synapse.orchestrator.policy import PolicyEngine
from synapse.core.binding import BindingManager
from synapse.core.workflow_engine import WorkflowDefinition
from synapse.core.execution import SecureExecutionContext, SecureWorkflowExecutor

@dataclass
class OrchestratorAgent:
    binding_manager: BindingManager
    task_planner: Optional[TaskPlanner] = None
    policy_engine: Optional[PolicyEngine] = None
    observability: Optional[Any] = None
    
    async def plan_workflow(self, task: Task) -> Optional[WorkflowDefinition]:
        """
        Convert task to executable workflow
        """
        if not self.task_planner:
            self.task_planner = TaskPlanner()
        
        return self.task_planner.plan(task, self.binding_manager)
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """
        Execute task through orchestrator pipeline
        """
        
        start_time = time.time()
        
        try:
            # 1. Validate task
            if not await self._validate_task(task):
                return {
                    "success": False,
                    "error": "Task validation failed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "protocol_version": "1.0"
                }
            
            # 2. Plan workflow
            workflow = await self.plan_workflow(task)
            if not workflow:
                return {
                    "success": False,
                    "error": "Workflow planning failed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "protocol_version": "1.0"
                }
            
            # 3. Create execution context
            context = SecureExecutionContext(
                agent_id=task.agent_id,
                capabilities=await self._get_agent_capabilities(task.agent_id),
                execution_seed=task.execution_seed
            )
            
            # 4. Execute
            executor = SecureWorkflowExecutor(
                binding_manager=self.binding_manager
            )
            
            result = await executor.execute(workflow, context)
            duration = time.time() - start_time
            
            # 5. Observability
            await self._record_execution(task, result, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            return {
                "success": False,
                "error": str(e),
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "protocol_version": "1.0"
            }
    
    async def _validate_task(self, task: Task) -> bool:
        if not task.agent_id or not task.description:
            return False
            
        if self.policy_engine:
            return await self.policy_engine.validate_task(task)
            
        return True
    
    async def _get_agent_capabilities(self, agent_id: str) -> List[str]:
        return list(self.binding_manager.get_agent_capabilities(agent_id))
    
    async def _record_execution(self, task: Task, result: Dict, duration: float):
        if self.observability:
            await self.observability.emit("task_executed", {
                "task_id": task.id,
                "agent_id": task.agent_id,
                "result": result,
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat()
            })
