"""
Task Planner for creating workflows from tasks
"""

from synapse.orchestrator.task_model import Task
from synapse.core.workflow_engine import WorkflowDefinition, Step
from typing import List, Dict, Any

class TaskPlanner:
    """Plans tasks into workflows"""
    
    def plan(self, task: Task, binding_manager) -> WorkflowDefinition:
        """Plan task into workflow definition"""
        # Create a simple workflow from the task
        steps = []
        
        # Create a single step based on task capabilities
        if task.required_capabilities or task.capabilities:
            caps = task.required_capabilities or task.capabilities
            step = Step(
                id="step_1",
                name=f"Execute: {task.description[:50]}",
                capabilities=list(caps) if isinstance(caps, (list, set)) else [caps],
                action="execute"
            )
            steps.append(step)
        
        workflow = WorkflowDefinition(
            name=f"Workflow for task {task.id[:8]}",
            steps=steps,
            required_capabilities=list(task.required_capabilities or task.capabilities or []),
            description=task.description
        )
        
        return workflow
