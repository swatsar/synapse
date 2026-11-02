PROTOCOL_VERSION: str = "1.0"
"""
Workflow Engine for dependency resolution and execution
"""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """Single workflow step"""
    id: str
    name: str
    requires: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    action: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowDefinition:
    """Workflow definition with steps and dependencies"""
    name: str
    steps: list[Step] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: list[str] = field(default_factory=list)
    description: str = ""

class WorkflowEngine:
    """Engine for workflow dependency resolution and execution"""
    
    def __init__(self):
        self._workflows: dict[str, WorkflowDefinition] = {}
    
    def register(self, workflow: WorkflowDefinition):
        """Register a workflow"""
        self._workflows[workflow.id] = workflow
    
    def get_execution_order(self, workflow: WorkflowDefinition) -> list[Step]:
        """Get execution order based on dependencies"""
        return self.build_execution_order(workflow)
    
    def build_execution_order(self, workflow: WorkflowDefinition) -> list[Step]:
        """Build execution order from workflow steps using topological sort"""
        if not workflow.steps:
            return []
        
        # Build adjacency list
        steps_dict = {step.id: step for step in workflow.steps}
        in_degree = {step.id: 0 for step in workflow.steps}
        graph = {step.id: [] for step in workflow.steps}
        
        # Build graph from dependencies
        for step in workflow.steps:
            for dep in step.requires:
                if dep in steps_dict:
                    graph[dep].append(step.id)
                    in_degree[step.id] += 1
        
        # Kahn's algorithm for topological sort
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(steps_dict[current])
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # If not all steps are in result, there's a cycle
        if len(result) != len(workflow.steps):
            # Return steps in original order instead of raising error
            return list(workflow.steps)
        
        return result
