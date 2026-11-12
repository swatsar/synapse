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
from typing import Any

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
logger = logging.getLogger(__name__)


def is_self_inspection_request(task_lower: str) -> bool:
    """Detect a request to study Synapse itself, not the user or a project.

    Kept as a module-level function so the orchestrator can enforce the same
    deterministic route even when no planner is available. A generic chat
    fallback must never answer a self-inspection request with advice addressed
    to the user.
    """
    triggers = (
        "изучи себя", "изучи самого себя", "исследуй себя",
        "проанализируй себя", "проверь себя", "оцени себя",
        "самоинспекц", "самоанализ", "что можно улучшить в тебе",
        "что улучшить в тебе", "твои слабые места", "твои недостатки",
        "твои ошибки", "как ты развиваешься", "как ты обучаешься",
        "твой рост", "твоя сеть роста", "как тебе улучшиться",
        "что ты узнал", "что ты узнала", "чему ты научился",
        "чему ты научилась", "чему научился", "чему научилась",
        "что ты выучил", "что ты выучила", "что ты запомнил",
        "что ты запомнила", "что ты усвоил", "что ты усвоила",
        "какие знания ты получил", "какие знания ты получила",
        "study yourself", "analyze yourself", "inspect yourself",
        "self-inspect", "self-review", "self-assessment",
        "improve yourself", "your weaknesses", "how do you learn",
        "what did you learn", "what have you learned",
        "how are you developing",
    )
    if not any(trigger in task_lower for trigger in triggers):
        return False
    code_targets = (
        "приложение", "проект", "код", "репозитор", "workspace",
        "codebase", "project", "repo",
    )
    self_targets = (
        "себя", "самого себя", "свои", "своих", "своей", "своё",
        "своего", "yourself", "your own",
    )
    if (
        any(target in task_lower for target in code_targets)
        and not any(target in task_lower for target in self_targets)
    ):
        return False
    return True


@dataclass
class ActionStep:
    """One step in an ActionPlan."""
    step_id: str
    action: str
    skill: str
    params: dict[str, Any] = field(default_factory=dict)
    required_capabilities: list[str] = field(default_factory=list)
    risk_level: int = 1
    depends_on: list[str] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
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
    steps: list[ActionStep] = field(default_factory=list)
    risk_level: int = 1
    required_capabilities: list[str] = field(default_factory=list)
    memory_context: list[dict] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
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

IMPORTANT INTERPRETATION RULES:
- "изучи приложение", "изучи рабочую среду", "проведи аудит", "исследуй проект" means read-only workspace inspection first: inventory files, inspect entry points/configuration, run safe static checks, then report evidence and recommendations.
- "модифицируй себя", "измени свои веса", "обучи себя" does not grant permission to alter the running model or base weights. Explain the boundary and, if useful, plan a proposal, dataset/eval, or adapter training workflow requiring explicit approval and holdout promotion gate.
- Never claim that a scan, code change, training run, or model modification happened unless a corresponding tool result proves it.

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
        self, task: str, context: dict | None = None
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
        # Self-inspection is deterministic and must not be re-written by a
        # planner LLM: a model can replace a grounded self-report with generic
        # advice. Explicit delegation to an external agent still wins inside
        # the heuristic.
        if self._match_self_inspection_request(task.lower()):
            steps = self._plan_heuristic(task, context)
        elif self.llm:
            steps = await self._plan_with_llm(task, memory_context, available)
        else:
            steps = self._plan_heuristic(task, context)

        # Step 4: Assemble
        all_caps: list[str] = []
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

    async def _recall_relevant(self, task: str) -> list[dict]:
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
        except (RuntimeError, ValueError, TypeError) as e:
            logger.warning("Memory recall failed: %s", e)
            return []

    async def _get_available_skills(self) -> list[str]:
        """Get list of active skill names from registry."""
        if not self.skill_registry:
            return ["read_file", "write_file", "web_search", "code_generator"]
        try:
            skills = await self.skill_registry.list_active()
            return [s.get("name", "") for s in skills if s.get("name")]
        except RuntimeError:
            return []

    async def _plan_with_llm(
        self,
        task: str,
        memory_context: list[dict],
        available_skills: list[str],
    ) -> list[ActionStep]:
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
        except (json.JSONDecodeError, RuntimeError, ValueError, TypeError) as e:
            logger.warning("LLM planning failed: %s", e)
            return self._plan_heuristic(task)

    def _plan_heuristic(
        self, task: str, context: dict | None = None,
    ) -> list[ActionStep]:
        """Heuristic plan generation based on task keywords."""
        t = task.lower()
        steps: list[ActionStep] = []
        payload = ((context or {}).get("perceived") or {}).get("metadata") or {}
        agent_request = payload.get("executor") or self._match_agent_request(t)
        self_inspection_request = (
            not agent_request and self._match_self_inspection_request(t)
        )
        self_study_request = (
            not agent_request
            and not self_inspection_request
            and self._match_self_study_request(t)
        )
        audit_request = any(k in t for k in ("изучи свое приложение", "изучи приложение", "рабочую среду", "проведи аудит", "исследуй проект", "audit the project", "inspect the workspace"))
        self_change_request = any(k in t for k in ("модифицируй себя", "изменить свои веса", "измени свои веса", "обучи себя", "modify yourself", "change your weights"))

        if self_inspection_request:
            steps.append(ActionStep(
                step_id="step_1",
                action="Report real Synapse growth, training and autonomy state",
                skill="self_inspection",
                params={"focus": task, "path": payload.get("path", ".")},
                required_capabilities=["memory:read", "fs:read"], risk_level=1,
            ))
            return steps

        if self_study_request:
            steps.append(ActionStep(
                step_id="step_1",
                action="Study project documentation and add grounded verified experience",
                skill="self_study",
                params={
                    "path": payload.get("path", "."),
                    "max_records": int(payload.get("max_records") or 8),
                },
                required_capabilities=["fs:read"], risk_level=1,
            ))
            return steps

        if audit_request:
            steps.append(ActionStep(
                step_id="step_1", action="Inspect workspace files and application structure", skill="workspace_audit",
                params={"path": payload.get("path", "."), "read_only": True},
                required_capabilities=["fs:read"], risk_level=1,
            ))
            if any(k in t for k in ("безопас", "security", "уязвим", "vulnerability")):
                steps.append(ActionStep(
                    step_id="step_2", action="Run read-only security audit", skill="security_audit",
                    params={"target_dir": payload.get("path", ".")},
                    required_capabilities=["fs:read"], risk_level=1,
                ))
            return steps

        if self_change_request:
            # A self-change request phrased as learning/training runs the real
            # adapter learning loop; bare "change your weights" stays a boundary
            # explanation, because base weights are never edited live.
            wants_training = any(k in t for k in ("обучи", "научи", "выучи", "train", "teach", "learn")) or payload.get("learning_topic")
            if wants_training:
                topic = str(payload.get("learning_topic") or self._match_learning_request(t) or "общий диалог")
                learning_params: dict[str, Any] = {
                    "topic": topic,
                    "language": payload.get("language", "Russian"),
                    "max_cycles": payload.get("max_cycles", 3),
                }
                if payload.get("teacher"):
                    learning_params["teacher"] = str(payload["teacher"])
                steps.append(ActionStep(
                    step_id="step_1", action=f"Run learning loop for topic '{topic}'", skill="learning_loop",
                    params=learning_params,
                    required_capabilities=["memory:read", "fs:read", "fs:write"], risk_level=2,
                ))
                return steps
            steps.append(ActionStep(
                step_id="step_1", action="Explain model and weight modification boundary", skill="generic_executor",
                params={"task": task, "max_new_tokens": 2048, "safety_boundary": "no_self_modification"},
                required_capabilities=["memory:read"], risk_level=1,
            ))
            return steps

        # Delegate to an installed external coding agent (Claude Code / Codex)
        # when the user asks to interact with them or hand the task over.
        if agent_request:
            agent_id = str(agent_request)
            if agent_id.startswith("agent:"):
                agent_id = agent_id.split(":", 1)[1]
            if agent_id in {"codex", "claude_code"}:
                step_params: dict[str, Any] = {"agent": agent_id, "task": task}
                model = payload.get("model")
                if isinstance(model, str) and model.strip() and not str(model).startswith(("llama", "codellama")):
                    step_params["model"] = model.strip()
                steps.append(ActionStep(
                    step_id="step_1", action=f"Delegate task to external agent {agent_id}", skill="external_agent",
                    params=step_params,
                    required_capabilities=["fs:read", "os:process"], risk_level=2,
                ))
                return steps

        # Chat-driven learning loop: teach the local model a topic through the
        # verified generate → snapshot → LoRA cycle while holdout improves.
        learning_topic = self._match_learning_request(t)
        if learning_topic is not None:
            learning_params = {
                "topic": learning_topic,
                "language": payload.get("language", "Russian"),
                "max_cycles": payload.get("max_cycles", 3),
            }
            if payload.get("teacher"):
                learning_params["teacher"] = str(payload["teacher"])
            steps.append(ActionStep(
                step_id="step_1", action=f"Run learning loop for topic '{learning_topic}'", skill="learning_loop",
                params=learning_params,
                required_capabilities=["memory:read", "fs:read", "fs:write"], risk_level=2,
            ))
            return steps

        if any(k in t for k in ["read", "open", "load", "get file"]):
            path = payload.get("path")
            if not path:
                # Prefer an explicit quoted path, then an absolute Windows
                # path, then the first path-like token with an extension. The
                # old greedy ``[\w -]+`` regex swallowed the leading verb
                # ("Read README.md" -> path "Read README.md") and made every
                # natural read-and-write task fail.
                quoted = re.search(r'''["']([^"']+)["']''', task)
                windows_path = re.search(r"[A-Za-z]:[\\/][^\s\"']+", task)
                if quoted:
                    path = quoted.group(1)
                elif windows_path:
                    path = windows_path.group(0)
                else:
                    candidates = re.findall(
                        r"(?:\.{0,2}[\\/])?[\w.-]+(?:[\\/][\w.-]+)*\.\w+", task
                    )
                    path = candidates[0] if candidates else "."
            steps.append(ActionStep(
                step_id="step_1", action="Read file contents", skill="read_file",
                params={"path": path},
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
                required_capabilities=["code:generate"], risk_level=2,
            ))
        if any(k in t for k in ["analyze", "process", "transform", "convert"]):
            steps.append(ActionStep(
                step_id=f"step_{len(steps)+1}", action="Analyze and process data", skill="data_processor",
                params={"task": task, "model": payload.get("model")},
                required_capabilities=["memory:read", "memory:write"], risk_level=2,
            ))
        if not steps:
            steps.append(ActionStep(
                step_id="step_1", action=f"Execute: {task[:60]}", skill="generic_executor",
                params={
                    "task": task,
                    "model": payload.get("model"),
                    "max_new_tokens": payload.get("max_new_tokens"),
                },
                required_capabilities=["memory:read"], risk_level=1,
            ))
        return steps

    def _match_agent_request(self, task_lower: str) -> str | None:
        """Detect a request to interact with an external coding agent CLI."""
        agent_names = {
            "claude code": "claude_code",
            "claude_code": "claude_code",
            "клод код": "claude_code",
            "кодекс": "codex",
            "codex": "codex",
        }
        cues = (
            "подключи", "запусти", "спроси", "попроси", "через", "передай",
            "connect", "run", "ask", "delegate", "use", "интерфейс",
        )
        for name, agent_id in agent_names.items():
            if name not in task_lower:
                continue
            if any(cue in task_lower for cue in cues):
                return agent_id
        if any(k in task_lower for k in ("внешний агент", "external agent", "внешнего агента")):
            return "codex"
        return None

    def _match_self_inspection_request(self, task_lower: str) -> bool:
        """Detect a request to study Synapse itself, not the user or a project.

        This must not hijack code or workspace audits: "изучи проект" is a
        workspace inspection, while "изучи себя" is a request for a grounded
        self-report about the agent's growth and training state.
        """
        return is_self_inspection_request(task_lower)

    def _match_self_study_request(self, task_lower: str) -> bool:
        """Detect a request to learn from the project's own documentation.

        This is deliberately narrower than "read": plain file reading remains
        ``read_file``. The route is for study requests that should add verified
        experience, for example "изучи документацию и стань умнее".
        """
        doc_cues = (
            "документац", "readme", "архитектур", "documentation",
            "architecture", "docs",
        )
        study_cues = (
            "изучи", "изуч", "обучись", "научись", "стань умнее",
            "пополни знания", "study", "learn from",
        )
        return any(cue in task_lower for cue in doc_cues) and any(
            cue in task_lower for cue in study_cues
        )

    def _match_learning_request(self, task_lower: str) -> str | None:
        """Detect a chat learning request and extract the topic, if any.

        A question about what was learned from a previous task is *not* a new
        learning request. Otherwise a follow-up like "а что ты узнал, когда
        выполнял задание: 'научись X'?" re-enters the loop because the quoted
        previous task contains a learning verb.
        """
        if re.search(
            r"(?:что|чему|как)\s+ты\s+(?:узнал|выучил|научил(?:ся)?|понял|запомнил)",
            task_lower,
        ):
            return None
        if re.search(r"what\s+did\s+you\s+(?:learn|study|train)", task_lower):
            return None
        triggers = (
            "научи", "обучи", "выучи", "научись", "потренируй", "обучение",
            "teach", "learn", "train",
        )
        if not any(trigger in task_lower for trigger in triggers):
            return None
        # Require an instruction, not a mention inside a quoted fragment or a
        # general question about learning. This keeps "научи меня X" and
        # "хочу научиться X" working while ignoring "расскажи, как учат X".
        head = task_lower.lstrip(" \t\n.,!?;:—-«\"'")
        imperative = re.match(
            r"^(?:пожалуйста[,\s]+)?"
            r"(?:научи(?:сь)?|обучи(?:сь)?|выучи|потренируй|обучени\w*|"
            r"teach|train|learn)(?:\s|$|[,.!?:;])",
            head,
        )
        contextual = re.match(
            r"^(?:я\s+хочу|хочу|помоги(?:\s+мне)?|давай|мне\s+нужно|"
            r"i\s+want\s+to|help\s+me|please)\b",
            head,
        )
        if not (imperative or contextual):
            return None
        for cue in ("меня", "me", "модель", "model", "себя"):
            task_lower = task_lower.replace(cue, " ", 1)
        topic = re.sub(
            r"(научи|обучи|выучи|научись|потренируй|обучение|teach|learn|train)[ingа-яё]*\s*",
            " ", task_lower, count=1,
        ).strip(" :,.!?\"'")
        return topic if topic else "общий диалог"

    def _assess_risk(self, task: str, steps: list[ActionStep]) -> int:
        return max((s.risk_level for s in steps), default=1)

    def _extract_capabilities(self, steps: list[ActionStep]) -> list[str]:
        caps: list[str] = []
        for s in steps:
            caps.extend(s.required_capabilities)
        return list(set(caps))

    async def _generate_steps_with_llm(self, task: str) -> list[ActionStep]:
        return await self._plan_with_llm(task, [], [])

    async def _generate_steps_heuristic(self, task: str) -> list[ActionStep]:
        return self._plan_heuristic(task)
