"""Planner Agent — task decomposition with LLM.

Protocol Version: 1.0
Specification: 3.1

Builds ActionPlan by:
1. Querying semantic memory for relevant past experience
2. Calling LLM with structured prompt to decompose task into steps
3. Determining risk level and required capabilities per step
4. Falling back to heuristic planning when LLM unavailable
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
logger = logging.getLogger(__name__)


@dataclass
class ActionStep:
    """One step in an ActionPlan."""
    step_id: str
    action: str
    skill: str
    params: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: int = 1
    depends_on: List[str] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "skill": self.skill,
            "params": self.params,
            "required_capabilities": self.required_capabilities,
            "risk_level": self.risk_level,
            "depends_on": self.depends_on,
            "protocol_version": self.protocol_version,
        }


@dataclass
class ActionPlan:
    """Complete execution plan for a task."""
    plan_id: str
    task: str
    steps: List[ActionStep] = field(default_factory=list)
    risk_level: int = 1
    required_capabilities: List[str] = field(default_factory=list)
    memory_context: List[Dict] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task": self.task,
            "steps": [s.to_dict() for s in self.steps],
            "risk_level": self.risk_level,
            "required_capabilities": self.required_capabilities,
            "memory_context_count": len(self.memory_context),
            "protocol_version": self.protocol_version,
        }


PLAN_PROMPT = """You are a Planner Agent for an autonomous AI platform.

TASK: {task}

RELEVANT MEMORY (from past executions):
{memory_context}

AVAILABLE SKILLS:
{available_skills}

Decompose the task into concrete steps. Return a JSON object:
{{
  "steps": [
    {{
      "step_id": "step_1",
      "action": "human-readable description",
      "skill": "skill_name",
      "params": {{"key": "value"}},
      "required_capabilities": ["fs:read", "net:http"],
      "risk_level": 1
    }}
  ],
  "risk_level": 2,
  "reasoning": "why this plan"
}}

Risk levels: 1=safe, 2=low, 3=medium, 4=high, 5=critical.
Capabilities: fs:read, fs:write, fs:delete, net:http, net:scan, os:process, iot:control, sys:info.

Return ONLY valid JSON, no markdown."""


class PlannerAgent:
    """Decomposes tasks into executable ActionPlans.

    Uses semantic memory to enrich planning context.
    Uses LLM for intelligent decomposition with fallback to heuristics.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        llm_provider: Any = None,
        memory_store: Any = None,
        skill_registry: Any = None,
        audit_logger: Any = None,
    ):
        self.llm = llm_provider
        self.memory = memory_store
        self.skill_registry = skill_registry
        self.audit_logger = audit_logger
        audit(
            event="planner_agent_initialized",
            has_llm=llm_provider is not None,
            has_memory=memory_store is not None,
            protocol_version=self.protocol_version,
        )

    async def create_plan(
        self, task: str, context: Optional[Dict] = None
    ) -> ActionPlan:
        """Create an ActionPlan for the given task.

        Steps:
        1. Recall relevant memories
        2. Get available skills
        3. LLM planning (or heuristic)
        4. Assemble ActionPlan
        """
        import uuid
        plan_id = str(uuid.uuid4())[:8]
        context = context or {}

        audit(
            event="plan_creation_started",
            plan_id=plan_id,
            task_preview=task[:80],
            protocol_version=self.protocol_version,
        )

        # Step 1: Recall
        memory_context = await self._recall_relevant(task)

        # Step 2: Available skills
        available = await self._get_available_skills()

        # Step 3: Generate steps
        if self.llm:
            steps = await self._plan_with_llm(task, memory_context, available)
        else:
            steps = self._plan_heuristic(task)

        # Step 4: Assemble
        all_caps: List[str] = []
        max_risk = 1
        for s in steps:
            all_caps.extend(s.required_capabilities)
            max_risk = max(max_risk, s.risk_level)

        plan = ActionPlan(
            plan_id=plan_id,
            task=task,
            steps=steps,
            risk_level=max_risk,
            required_capabilities=list(set(all_caps)),
            memory_context=memory_context,
        )

        audit(
            event="plan_creation_completed",
            plan_id=plan_id,
            steps_count=len(steps),
            risk_level=max_risk,
            protocol_version=self.protocol_version,
        )

        return plan

    async def _recall_relevant(self, task: str) -> List[Dict]:
        """Query semantic memory for related past experiences."""
        if not self.memory:
            return []
        try:
            # Try vector store first
            if hasattr(self.memory, "vector_store") and self.memory.vector_store:
                results = await self.memory.vector_store.query(task, limit=3)
                return results
            # Fallback to basic search
            results = await self.memory.search(task)
            return results[:3]
        except Exception as e:
            logger.warning("Memory recall failed: %s", e)
            return []

    async def _get_available_skills(self) -> List[str]:
        """Get list of active skill names from registry."""
        if not self.skill_registry:
            return ["read_file", "write_file", "web_search", "code_generator"]
        try:
            skills = await self.skill_registry.list_active()
            return [s.get("name", "") for s in skills if s.get("name")]
        except Exception:
            return []

    async def _plan_with_llm(
        self,
        task: str,
        memory_context: List[Dict],
        available_skills: List[str],
    ) -> List[ActionStep]:
        """Use LLM to decompose task into steps."""
        memory_text = "\n".join(
            f"- {m.get('text', m)}" for m in memory_context[:3]
        ) or "None available"
        skills_text = ", ".join(available_skills) or "read_file, write_file, web_search"

        prompt = PLAN_PROMPT.format(
            task=task,
            memory_context=memory_text,
            available_skills=skills_text,
        )

        try:
            response = await self.llm.generate(prompt)
            content = response.get("content", "")
            content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(content)
            raw_steps = data.get("steps", [])
            steps = []
            for i, s in enumerate(raw_steps):
                steps.append(ActionStep(
                    step_id=s.get("step_id", f"step_{i+1}"),
                    action=s.get("action", ""),
                    skill=s.get("skill", ""),
                    params=s.get("params", {}),
                    required_capabilities=s.get("required_capabilities", []),
                    risk_level=int(s.get("risk_level", 1)),
                    depends_on=s.get("depends_on", []),
                ))
            return steps if steps else self._plan_heuristic(task)
        except Exception as e:
            logger.warning("LLM planning failed: %s", e)
            return self._plan_heuristic(task)

    def _plan_heuristic(self, task: str) -> List[ActionStep]:
        """Heuristic plan generation based on task keywords."""
        t = task.lower()
        steps: List[ActionStep] = []

        if any(k in t for k in ["read", "open", "load", "get file"]):
            steps.append(ActionStep(
                step_id="step_1", action="Read file contents", skill="read_file",
                params={"path": re.search(r'[\w./]+\.\w+', task).group(0) if re.search(r'[\w./]+\.\w+', task) else "."},
                required_capabilities=["fs:read"], risk_level=1,
            ))
        if any(k in t for k in ["write", "save", "create file", "output"]):
            steps.append(ActionStep(
                step_id=f"step_{len(steps)+1}", action="Write result to file", skill="write_file",
                params={"path": "output.txt", "content": "{{previous_result}}"},
                required_capabilities=["fs:write"], risk_level=2,
            ))
        if any(k in t for k in ["search", "find", "look up", "web", "google"]):
            steps.append(ActionStep(
                step_id=f"step_{len(steps)+1}", action="Web search", skill="web_search",
                params={"query": task},
                required_capabilities=["net:http"], risk_level=2,
            ))
        if any(k in t for k in ["generate", "create", "build", "code", "script"]):
            steps.append(ActionStep(
                step_id=f"step_{len(steps)+1}", action="Generate code", skill="code_generator",
                params={"task_description": task},
                required_capabilities=["code:generate"], risk_level=3,
            ))
        if any(k in t for k in ["analyze", "process", "transform", "convert"]):
            steps.append(ActionStep(
                step_id=f"step_{len(steps)+1}", action="Analyze and process data", skill="data_processor",
                params={"task": task},
                required_capabilities=["memory:read", "memory:write"], risk_level=2,
            ))
        if not steps:
            steps.append(ActionStep(
                step_id="step_1", action=f"Execute: {task[:60]}", skill="generic_executor",
                params={"task": task},
                required_capabilities=["memory:read"], risk_level=1,
            ))
        return steps

    def _assess_risk(self, task: str, steps: List[ActionStep]) -> int:
        return max((s.risk_level for s in steps), default=1)

    def _extract_capabilities(self, steps: List[ActionStep]) -> List[str]:
        caps: List[str] = []
        for s in steps:
            caps.extend(s.required_capabilities)
        return list(set(caps))

    async def _generate_steps_with_llm(self, task: str) -> List[ActionStep]:
        return await self._plan_with_llm(task, [], [])

    async def _generate_steps_heuristic(self, task: str) -> List[ActionStep]:
        return self._plan_heuristic(task)
