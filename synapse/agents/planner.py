"""Planner Agent for task decomposition.

Implements SYSTEM_SPEC_v3.1 - Planner Agent.
With comprehensive audit logging.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


@dataclass
class ActionStep:
    """Single action step in a plan."""
    action: str
    skill: str
    params: Dict
    protocol_version: str = "1.0"


@dataclass
class ActionPlan:
    """Complete action plan."""
    task: str
    steps: List[ActionStep]
    risk_level: int
    required_capabilities: List[str]
    protocol_version: str = "1.0"


class PlannerAgent:
    """Agent for planning and task decomposition with audit logging."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, llm_provider=None, memory_store=None, audit_logger=None):
        self.llm = llm_provider
        self.memory = memory_store
        self.audit_logger = audit_logger

        # Audit: planner agent initialized
        audit(
            event="planner_agent_initialized",
            has_llm_provider=llm_provider is not None,
            has_memory_store=memory_store is not None,
            protocol_version=self.protocol_version
        )

    async def create_plan(self, task: str, context: Dict = None) -> ActionPlan:
        """Create execution plan from task with audit logging.

        Args:
            task: Task description
            context: Execution context

        Returns:
            ActionPlan with steps
        """
        # Audit: plan creation started
        audit(
            event="plan_creation_started",
            task_length=len(task),
            protocol_version=self.protocol_version
        )

        # Generate plan steps
        if self.llm:
            steps = await self._generate_steps_with_llm(task)
        else:
            steps = await self._generate_steps_heuristic(task)

        # Determine risk level
        risk_level = self._assess_risk(task, steps)

        # Determine required capabilities
        capabilities = self._extract_capabilities(steps)

        plan = ActionPlan(
            task=task,
            steps=steps,
            risk_level=risk_level,
            required_capabilities=capabilities,
            protocol_version=self.protocol_version
        )

        # Audit: plan creation completed
        audit(
            event="plan_creation_completed",
            steps_count=len(steps),
            risk_level=risk_level,
            capabilities_count=len(capabilities),
            protocol_version=self.protocol_version
        )

        return plan

    async def _generate_steps_with_llm(self, task: str) -> List[ActionStep]:
        """Generate steps using LLM."""
        prompt = f"""Create a step-by-step plan for this task:

Task: {task}

Provide steps as JSON array with:
- action: action name
- skill: skill to use
- params: parameters

Protocol Version: {self.protocol_version}
"""

        response = await self.llm.generate(prompt)

        # Parse response into steps
        steps = []
        # Mock parsing for now
        steps.append(ActionStep(
            action="analyze",
            skill="text_analysis",
            params={"text": task},
            protocol_version=self.protocol_version
        ))

        return steps

    async def _generate_steps_heuristic(self, task: str) -> List[ActionStep]:
        """Generate steps using heuristics."""
        steps = []

        # Simple heuristic: analyze then execute
        steps.append(ActionStep(
            action="analyze",
            skill="text_analysis",
            params={"text": task},
            protocol_version=self.protocol_version
        ))

        steps.append(ActionStep(
            action="execute",
            skill="general_executor",
            params={"task": task},
            protocol_version=self.protocol_version
        ))

        return steps

    def _assess_risk(self, task: str, steps: List[ActionStep]) -> int:
        """Assess risk level of plan."""
        # Simple heuristic based on keywords
        high_risk_keywords = ['delete', 'remove', 'format', 'drop', 'execute', 'system']

        task_lower = task.lower()
        for keyword in high_risk_keywords:
            if keyword in task_lower:
                return 3

        return 1

    def _extract_capabilities(self, steps: List[ActionStep]) -> List[str]:
        """Extract required capabilities from steps."""
        capabilities = set()

        for step in steps:
            # Map skills to capabilities
            if 'file' in step.skill.lower():
                capabilities.add("fs:read:/workspace/**")
                capabilities.add("fs:write:/workspace/**")
            if 'web' in step.skill.lower() or 'http' in step.skill.lower():
                capabilities.add("network:http")

        return list(capabilities)
