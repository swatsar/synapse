"""Orchestrator – 8-Step Cognitive Cycle Implementation.
Spec v3.1 compliant.

Cognitive Cycle:
1. PERCEIVE  - Восприятие события
2. RECALL    - Извлечение из памяти
3. PLAN      - Планирование действий
4. SECURITY  - Проверка capabilities
5. ACT       - Выполнение плана
6. OBSERVE   - Наблюдение результата
7. EVALUATE  - Оценка выполнения
8. LEARN     - Обучение
"""
import inspect
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synapse.observability.logger import audit

from .determinism import DeterministicIDGenerator, DeterministicSeedManager

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
_progress_context: ContextVar[Callable[[str, dict[str, Any]], Awaitable[None] | None] | None] = ContextVar(
    "synapse_progress_callback", default=None,
)


class CognitiveCycleResult:
    """Result of cognitive cycle execution."""
    
    def __init__(
        self,
        success: bool,
        perceived: dict | None = None,
        recalled: dict | None = None,
        plan: dict | None = None,
        security_result: dict | None = None,
        action_result: dict | None = None,
        observation: dict | None = None,
        evaluation: dict | None = None,
        learning: dict | None = None,
        error: str | None = None
    ):
        self.success = success
        self.perceived = perceived
        self.recalled = recalled
        self.plan = plan
        self.security_result = security_result
        self.action_result = action_result
        self.observation = observation
        self.evaluation = evaluation
        self.learning = learning
        self.error = error
        self.protocol_version = PROTOCOL_VERSION
        self.timestamp = datetime.now(UTC).isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "perceived": self.perceived,
            "recalled": self.recalled,
            "plan": self.plan,
            "security_result": self.security_result,
            "action_result": self.action_result,
            "observation": self.observation,
            "evaluation": self.evaluation,
            "learning": self.learning,
            "error": self.error,
            "protocol_version": self.protocol_version,
            "timestamp": self.timestamp
        }


class Orchestrator:
    """Orchestrator implementing the 8-step cognitive cycle.
    
    The cognitive cycle follows the pattern:
    PERCEIVE → RECALL → PLAN → SECURITY → ACT → OBSERVE → EVALUATE → LEARN
    
    Each step is logged for audit and can be checkpointed for rollback.
    """

    protocol_version: str = "1.0"

    def __init__(
        self,
        seed_manager: DeterministicSeedManager,
        id_generator: DeterministicIDGenerator,
        memory_store: Any | None = None,
        security_manager: Any | None = None,
        skill_registry: Any | None = None,
        checkpoint_manager: Any | None = None,
        planner: Any | None = None,
        critic: Any | None = None,
        learning_engine: Any | None = None,
        progress_callback: Callable[[str, dict[str, Any]], Awaitable[None] | None] | None = None,
    ):
        self.protocol_version = "1.0"
        self.seed_manager = seed_manager
        self.id_generator = id_generator
        self.memory_store = memory_store
        self.security_manager = security_manager
        self.skill_registry = skill_registry
        self.checkpoint_manager = checkpoint_manager
        self.planner = planner
        self.critic = critic
        self.learning_engine = learning_engine
        self.progress_callback = progress_callback

        # Audit: orchestrator initialized
        audit(
            event="orchestrator_initialized",
            protocol_version=self.protocol_version,
            spec_version=SPEC_VERSION,
            cognitive_cycle="8-step"
        )

    # =========================================================================
    # 8-STEP COGNITIVE CYCLE
    # =========================================================================

    async def _emit_progress(self, step: str, status: str, **details: Any) -> None:
        """Publish coarse progress without changing the cycle's execution semantics."""
        callback = _progress_context.get() or self.progress_callback
        if callback is None:
            return
        try:
            result = callback(step, {"status": status, **details})
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            audit(event="progress_callback_error", error=str(exc), protocol_version=self.protocol_version)

    async def execute_cycle(self, event: dict[str, Any]) -> CognitiveCycleResult:
        """Execute a complete cognitive cycle on an event.

        This is the main orchestration method that implements the 8-step
        cognitive cycle: PERCEIVE → RECALL → PLAN → SECURITY → ACT → OBSERVE → EVALUATE → LEARN
        """
        progress_token = _progress_context.set(event.get("_progress_callback"))
        try:
            return await self._execute_cycle_steps(event)
        finally:
            _progress_context.reset(progress_token)

    async def _execute_cycle_steps(self, event: dict[str, Any]) -> CognitiveCycleResult:
        audit(
            event="cognitive_cycle_started",
            event_type=event.get("type", "unknown"),
            protocol_version=self.protocol_version
        )

        try:
            # Step 1: PERCEIVE
            await self._emit_progress("perceive", "running")
            perceived = await self._perceive(event)
            await self._emit_progress("perceive", "completed")

            # Step 2: RECALL
            await self._emit_progress("recall", "running")
            recalled = await self._recall(perceived)
            await self._emit_progress("recall", "completed", memories=len(recalled.get("episodic", [])))

            # Step 3: PLAN
            await self._emit_progress("plan", "running")
            plan = await self._plan(perceived, recalled)
            await self._emit_progress(
                "plan", "completed", steps=len(plan.get("steps", [])),
                risk_level=plan.get("risk_level", 1),
            )

            # Step 4: SECURITY CHECK
            await self._emit_progress("security", "running")
            security_result = await self._security_check(plan)
            await self._emit_progress(
                "security", "completed" if security_result.get("approved") else "failed",
                requires_approval=security_result.get("requires_human_approval", False),
            )
            
            if not security_result.get("approved", False):
                return CognitiveCycleResult(
                    success=False,
                    perceived=perceived,
                    recalled=recalled,
                    plan=plan,
                    security_result=security_result,
                    error="Security check failed",
                )
            if (
                security_result.get("requires_human_approval")
                and not event.get("_approval_granted", False)
            ):
                return CognitiveCycleResult(
                    success=False,
                    perceived=perceived,
                    recalled=recalled,
                    plan=plan,
                    security_result=security_result,
                    error="Human approval required",
                )

            if plan.get("risk_level", 0) >= 3 and self.checkpoint_manager:
                await self._create_checkpoint(event, plan)

            await self._emit_progress("act", "running")
            action_result = await self._act(
                plan,
                approval_granted=bool(event.get("_approval_granted", False)),
            )
            await self._emit_progress(
                "act", "completed" if action_result.get("success") else "failed",
                completed=action_result.get("steps_completed", 0),
                total=action_result.get("steps_total", 0),
            )
            await self._emit_progress("observe", "running")
            observation = await self._observe(action_result)
            await self._emit_progress("observe", "completed")
            await self._emit_progress("evaluate", "running")
            evaluation = await self._evaluate(plan, observation)
            await self._emit_progress("evaluate", "completed", score=evaluation.get("score"))
            await self._emit_progress("learn", "running")
            learning = await self._learn(event, plan, action_result, evaluation)
            await self._emit_progress("learn", "completed", stored=learning.get("stored", False))
            success = bool(action_result.get("success") and evaluation.get("success"))

            audit(
                event="cognitive_cycle_completed",
                success=success,
                protocol_version=self.protocol_version,
            )

            return CognitiveCycleResult(
                success=success,
                perceived=perceived,
                recalled=recalled,
                plan=plan,
                security_result=security_result,
                action_result=action_result,
                observation=observation,
                evaluation=evaluation,
                learning=learning,
                error=None if success else next(
                    (
                        item["error"]
                        for item in action_result.get("errors", [])
                        if item.get("error")
                    ),
                    "Task execution failed",
                ),
            )

        except Exception as e:
            audit(
                event="cognitive_cycle_error",
                error=str(e),
                protocol_version=self.protocol_version,
            )
            return CognitiveCycleResult(success=False, error=str(e))

    async def run_goal(self, goal: dict[str, Any]) -> CognitiveCycleResult:
        """Run a high-level goal through the cognitive cycle."""
        return await self.execute_cycle({
            "type": "goal",
            "data": goal,
            "_approval_granted": goal.get("_approval_granted", False),
        "metadata": goal.get("payload") or goal.get("metadata") or {},
            "timestamp": datetime.now(UTC).isoformat(),
        })

    async def _execute_full_cycle(self, event: dict[str, Any]) -> CognitiveCycleResult:
        """Backward-compatible alias for the canonical cognitive cycle."""
        return await self.execute_cycle(event)

    # -------------------------------------------------------------------------
    # Step 1: PERCEIVE
    # -------------------------------------------------------------------------
    
    async def _perceive(self, event: dict[str, Any]) -> dict[str, Any]:
        """Step 1: PERCEIVE - Восприятие события.
        
        Analyzes and normalizes the incoming event.
        
        Args:
            event: Raw input event
            
        Returns:
            Perceived event with normalized structure
        """
        audit(
            event="cognitive_step_perceive",
            event_type=event.get("type", "unknown"),
            protocol_version=self.protocol_version
        )
        
        perceived = {
            "event_id": str(uuid.uuid4()),
            "event_type": event.get("type", "unknown"),
            "content": event.get("content") or event.get("data", {}).get("task", ""),
            "source": event.get("source", "unknown"),
            "user_id": event.get("user_id"),
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": event.get("metadata", event.get("data", {}).get("payload") or {}),
            "protocol_version": self.protocol_version
        }
        
        return perceived

    # -------------------------------------------------------------------------
    # Step 2: RECALL
    # -------------------------------------------------------------------------
    
    async def _recall(self, perceived: dict[str, Any]) -> dict[str, Any]:
        """Step 2: RECALL - Извлечение из памяти.
        
        Retrieves relevant context from memory stores.
        
        Args:
            perceived: Perceived event from step 1
            
        Returns:
            Recalled context and relevant memories
        """
        audit(
            event="cognitive_step_recall",
            event_type=perceived.get("event_type"),
            protocol_version=self.protocol_version
        )
        
        recalled = {
            "episodic": [],
            "semantic": [],
            "procedural": [],
            "context": {},
            "protocol_version": self.protocol_version,
        }

        query_text = perceived.get("content", perceived.get("goals", [""])[0] if perceived.get("goals") else "")

        if self.memory_store and query_text:
            try:
                # Episodic: past similar events
                recalled["episodic"] = await self.memory_store.search(query_text[:80])
                # Semantic: vector similarity search (if vector store attached)
                if hasattr(self.memory_store, "vector_store") and self.memory_store.vector_store:
                    recalled["semantic"] = await self.memory_store.vector_store.query(query_text, limit=5)
                # Procedural: available skills
                if self.skill_registry:
                    try:
                        recalled["procedural"] = await self.skill_registry.list_active()
                    except Exception as _exc:  # noqa
                        pass  # noqa: silenced - _exc
            except Exception as e:
                audit(event="recall_memory_error", error=str(e), protocol_version=self.protocol_version)

        return recalled

    # -------------------------------------------------------------------------
    # Step 3: PLAN
    # -------------------------------------------------------------------------
    
    async def _plan(
        self,
        perceived: dict[str, Any],
        recalled: dict[str, Any]
    ) -> dict[str, Any]:
        """Step 3: PLAN - Планирование действий.
        
        Creates action plan based on perceived event and recalled context.
        
        Args:
            perceived: Perceived event from step 1
            recalled: Recalled context from step 2
            
        Returns:
            Action plan with steps and required capabilities
        """
        audit(
            event="cognitive_step_plan",
            event_type=perceived.get("event_type"),
            protocol_version=self.protocol_version
        )
        
        goal = perceived.get("content", "") or " ".join(perceived.get("goals", []))

        if self.planner and goal:
            try:
                action_plan = await self.planner.create_plan(
                    task=goal,
                    context={"recalled": recalled, "perceived": perceived},
                )
                return {
                    "goal": goal,
                    "plan_id": action_plan.plan_id,
                    "steps": [s.to_dict() for s in action_plan.steps],
                    "required_capabilities": action_plan.required_capabilities,
                    "risk_level": action_plan.risk_level,
                    "memory_context_count": len(action_plan.memory_context),
                    "protocol_version": self.protocol_version,
                }
            except Exception as e:
                audit(event="planner_error", error=str(e), protocol_version=self.protocol_version)

        # Heuristic fallback
        event_type = perceived.get("event_type", "unknown")
        caps = {
            "file_operation": ["fs:read", "fs:write"],
            "network_request": ["net:http"],
            "command_execution": ["os:process"],
        }.get(event_type, ["memory:read"])
        return {
            "goal": goal,
            "steps": [{"step_id": "step_1", "action": goal, "skill": "generic", "params": {}}],
            "required_capabilities": caps,
            "risk_level": {"command_execution": 4}.get(event_type, 1),
            "protocol_version": self.protocol_version,
        }

    # -------------------------------------------------------------------------
    # Step 4: SECURITY CHECK
    # -------------------------------------------------------------------------
    
    async def _security_check(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Step 4: SECURITY CHECK - Проверка capabilities.
        
        Validates that required capabilities are available and approved.
        
        Args:
            plan: Action plan from step 3
            
        Returns:
            Security check result with approval status
        """
        audit(
            event="cognitive_step_security_check",
            risk_level=plan.get("risk_level", 0),
            required_capabilities=plan.get("required_capabilities", []),
            protocol_version=self.protocol_version
        )
        
        security_result = {
            "approved": True,
            "requires_human_approval": False,
            "blocked_capabilities": [],
            "issues": [],
            "protocol_version": self.protocol_version
        }
        
        # Check if human approval is required for risk_level >= 3
        if plan.get("risk_level", 0) >= 3:
            security_result["requires_human_approval"] = True
            # In production, this would pause and wait for approval
        
        # If security manager is available, validate capabilities
        if self.security_manager:
            try:
                # Check each required capability
                required_caps = plan.get("required_capabilities", [])
                if required_caps:
                    result = await self.security_manager.check_capabilities(
                        required_capabilities=required_caps,
                        context={"agent_id": "orchestrator"},
                    )
                    if not result.approved:
                        security_result["approved"] = False
                        security_result["issues"].extend(result.blocked_capabilities)
            except Exception as e:
                security_result["approved"] = False
                security_result["issues"].append(str(e))
        
        return security_result

    # -------------------------------------------------------------------------
    # Step 5: ACT
    # -------------------------------------------------------------------------
    
    async def _act(
        self,
        plan: dict[str, Any],
        approval_granted: bool = False,
    ) -> dict[str, Any]:
        """Step 5: ACT - Выполнение плана.
        
        Executes the action plan using available skills.
        
        Args:
            plan: Action plan from step 3
            
        Returns:
            Action execution result
        """
        audit(
            event="cognitive_step_act",
            goal=plan.get("goal", "")[:100],
            protocol_version=self.protocol_version
        )
        
        action_result = {
            "success": False,
            "steps_completed": 0,
            "steps_total": len(plan.get("steps", [])),
            "outputs": [],
            "errors": [],
            "protocol_version": self.protocol_version,
        }

        if not self.skill_registry:
            action_result["errors"].append({
                "step": None,
                "skill": None,
                "error": "No skill registry configured",
            })
            return action_result

        from synapse.core.models import ExecutionContext

        capabilities = list(plan.get("required_capabilities", []))
        context = ExecutionContext(
            session_id=plan.get("plan_id", str(uuid.uuid4())),
            agent_id="orchestrator",
            trace_id=plan.get("plan_id", str(uuid.uuid4())),
            capabilities=capabilities,
            memory_store=self.memory_store,
            approval_granted=approval_granted,
        )

        for i, step in enumerate(plan.get("steps", [])):
            step_name = step.get("skill") or step.get("action") or f"step_{i}"
            try:
                step_result = await self.skill_registry.execute(
                    step_name,
                    context=context,
                    **step.get("params", {}),
                )
                if step_result.get("success") is False:
                    raise RuntimeError(step_result.get("error") or f"Skill failed: {step_name}")

                action_result["steps_completed"] += 1
                action_result["outputs"].append(step_result)
                audit(
                    event="step_executed",
                    step_id=step.get("step_id", str(i)),
                    skill=step_name,
                    status="completed",
                    protocol_version=self.protocol_version,
                )
            except Exception as e:
                action_result["errors"].append({
                    "step": i,
                    "skill": step_name,
                    "error": str(e),
                })
                audit(
                    event="step_failed",
                    step_id=str(i),
                    error=str(e),
                    protocol_version=self.protocol_version,
                )
                break

        action_result["success"] = (
            action_result["steps_total"] > 0
            and action_result["steps_completed"] == action_result["steps_total"]
            and not action_result["errors"]
        )
        return action_result

    # -------------------------------------------------------------------------
    # Step 6: OBSERVE
    # -------------------------------------------------------------------------
    
    async def _observe(self, action_result: dict[str, Any]) -> dict[str, Any]:
        """Step 6: OBSERVE - Наблюдение результата.
        
        Observes and analyzes the action execution result.
        
        Args:
            action_result: Result from step 5
            
        Returns:
            Observation with analysis
        """
        audit(
            event="cognitive_step_observe",
            success=action_result.get("success", False),
            protocol_version=self.protocol_version
        )
        
        observation = {
            "success": action_result.get("success", False),
            "steps_completed": action_result.get("steps_completed", 0),
            "steps_total": action_result.get("steps_total", 0),
            "outputs": action_result.get("outputs", []),
            "errors": action_result.get("errors", []),
            "has_errors": len(action_result.get("errors", [])) > 0,
            "error_count": len(action_result.get("errors", [])),
            "protocol_version": self.protocol_version
        }
        
        return observation

    # -------------------------------------------------------------------------
    # Step 7: EVALUATE
    # -------------------------------------------------------------------------
    
    async def _evaluate(
        self,
        plan: dict[str, Any],
        observation: dict[str, Any]
    ) -> dict[str, Any]:
        """Step 7: EVALUATE - Оценка выполнения.
        
        Evaluates the success of the action against the plan.
        
        Args:
            plan: Original action plan from step 3
            observation: Observation from step 6
            
        Returns:
            Evaluation with success metrics
        """
        audit(
            event="cognitive_step_evaluate",
            success=observation.get("success", False),
            protocol_version=self.protocol_version
        )
        
        task = plan.get("goal", "")
        act_result = {
            "status": "completed" if observation.get("success") else "error",
            "result": observation.get("outputs", [{}])[-1] if observation.get("outputs") else None,
            "error": observation.get("errors", [{}])[-1].get("error") if observation.get("errors") else None,
        }

        if self.critic:
            try:
                ev = await self.critic.evaluate(act_result, task=task)
                ev["completion_rate"] = (
                    observation.get("steps_completed", 0) / max(observation.get("steps_total", 1), 1)
                )
                ev["protocol_version"] = self.protocol_version
                return ev
            except Exception as e:
                audit(event="critic_error", error=str(e), protocol_version=self.protocol_version)

        # Heuristic fallback
        total = observation.get("steps_total", 0)
        done = observation.get("steps_completed", 0)
        rate = done / total if total else 1.0
        return {
            "success": observation.get("success", False),
            "score": rate,
            "completion_rate": rate,
            "issues": ["Errors occurred"] if observation.get("has_errors") else [],
            "recommendations": ["Consider alternative approach"] if not observation.get("success") else [],
            "protocol_version": self.protocol_version,
        }

    # -------------------------------------------------------------------------
    # Step 8: LEARN
    # -------------------------------------------------------------------------
    
    async def _learn(
        self,
        event: dict[str, Any],
        plan: dict[str, Any],
        action_result: dict[str, Any],
        evaluation: dict[str, Any]
    ) -> dict[str, Any]:
        """Step 8: LEARN - Обучение.
        
        Stores learnings from this execution for future use.
        
        Args:
            event: Original input event
            plan: Action plan from step 3
            action_result: Result from step 5
            evaluation: Evaluation from step 7
            
        Returns:
            Learning result with stored insights
        """
        audit(
            event="cognitive_step_learn",
            success=evaluation.get("success", False),
            protocol_version=self.protocol_version
        )
        
        learning = {
            "stored": False,
            "insights": [],
            "patterns": [],
            "create_skill_triggered": False,
            "protocol_version": self.protocol_version,
        }

        task = plan.get("goal", "")
        skill_name = plan.get("steps", [{}])[0].get("skill", "") if plan.get("steps") else ""

        if self.learning_engine:
            try:
                await self.learning_engine.process(
                    result={**action_result, **evaluation},
                    task=task,
                    skill_name=skill_name,
                )
                learning["stored"] = True
                learning["create_skill_triggered"] = evaluation.get("should_create_skill", False)
            except Exception as e:
                audit(event="learn_engine_error", error=str(e), protocol_version=self.protocol_version)
        
        # Always add an insight for successful execution (fallback when no memory_store)
        if evaluation.get("success") and not learning["insights"]:
            insight = {
                "type": "success_pattern",
                "task": task[:100],
                "score": evaluation.get("score", 1.0),
            }
            learning["insights"].append(insight)
            learning["stored"] = True
        
        if self.memory_store and not learning["insights"]:
            try:
                insight = {
                    "type": "success_pattern" if evaluation.get("success") else "failure_pattern",
                    "task": task[:100],
                    "score": evaluation.get("score", 0.0),
                }
                await self.memory_store.add_episodic(f"learn:{task[:40]}", insight)
                learning["stored"] = True
                learning["insights"].append(insight)
            except Exception as e:
                audit(event="learn_storage_error", error=str(e), protocol_version=self.protocol_version)

        return learning

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    async def _create_checkpoint(
        self,
        event: dict[str, Any],
        plan: dict[str, Any]
    ) -> str:
        """Create checkpoint before high-risk action.
        
        Args:
            event: Original event
            plan: Action plan
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid.uuid4())
        
        audit(
            event="checkpoint_created",
            checkpoint_id=checkpoint_id,
            risk_level=plan.get("risk_level", 0),
            protocol_version=self.protocol_version
        )
        
        if self.checkpoint_manager:
            try:
                if hasattr(self.checkpoint_manager, 'create'):
                    await self.checkpoint_manager.create(checkpoint_id, event, plan)
                elif hasattr(self.checkpoint_manager, 'create_checkpoint'):
                    self.checkpoint_manager.create_checkpoint(
                        agent_id=event.get("agent_id", "orchestrator"),
                        session_id=checkpoint_id
                    )
            except Exception:
                pass  # Checkpoint failure is non-fatal
        
        return checkpoint_id

    # =========================================================================
    # Legacy Methods (for backward compatibility)
    # =========================================================================

    async def handle(self, input_data: dict) -> dict:
        """Execute a task and report the actual cognitive-cycle outcome."""
        if not isinstance(input_data, dict) or not str(input_data.get("task", "")).strip():
            return {
                "status": "failed",
                "success": False,
                "error": "A non-empty task is required",
                "protocol_version": self.protocol_version,
            }

        audit(
            event="task_received",
            input_type=input_data.get("type", "unknown"),
            has_task=True,
            protocol_version=self.protocol_version,
        )
        task_id = self.id_generator.generate(input_data["task"])
        event = dict(input_data)
        event.setdefault("type", "goal")
        event["content"] = input_data["task"]
        event["metadata"] = input_data.get("payload") or input_data.get("metadata") or {}
        cycle = await self.execute_cycle(event)
        details = cycle.to_dict()
        status = (
            "approval_required"
            if cycle.error == "Human approval required"
            else "completed" if cycle.success else "failed"
        )
        audit(
            event="task_finished",
            task_id=str(task_id),
            status=status,
            protocol_version=self.protocol_version,
        )
        return {
            "task_id": str(task_id),
            "status": status,
            "success": cycle.success,
            "error": cycle.error,
            "result": details,
            "protocol_version": self.protocol_version,
        }

    def handle_error(self, input_data: dict, error: Exception) -> dict:
        """Handle errors with audit logging.

        Args:
            input_data: Input dictionary
            error: Exception that occurred

        Returns:
            Error result dictionary
        """
        audit(
            event="task_error",
            error_type=type(error).__name__,
            error_message=str(error)[:200],
            protocol_version=self.protocol_version
        )

        return {
            "status": "error",
            "error": str(error),
            "protocol_version": self.protocol_version
        }


# ---------------------------------------------------------------------------
# Factory function: wire up the full cognitive stack
# ---------------------------------------------------------------------------

def build_orchestrator(
    llm_model: str = "gpt-4o-mini",
    api_key: str | None = None,
    db_path: str | None = None,
    vector_persist_dir: str | None = None,
    workspace_root: str | None = None,
) -> "Orchestrator":
    """Build a fully-wired Orchestrator with all cognitive components.

    This is the production entry-point. All agents share a single MemoryStore
    and LLMProvider.
    """
    import os as _os

    from synapse.agents.critic import CriticAgent
    from synapse.agents.developer import DeveloperAgent
    from synapse.agents.planner import PlannerAgent
    from synapse.core.checkpoint import CheckpointManager
    from synapse.core.determinism import DeterministicIDGenerator, DeterministicSeedManager
    from synapse.core.models import SkillManifest
    from synapse.core.security import SecurityManager
    from synapse.learning.engine import LearningEngine
    from synapse.llm.provider import LiteLLMProvider
    from synapse.memory.store import MemoryStore
    from synapse.memory.vector_store import VectorMemoryStore
    from synapse.security.capability_manager import CapabilityManager as SkillCapabilityManager
    from synapse.skills.builtins.external_agent import execute_external_agent
    from synapse.skills.builtins.learning_loop import execute_learning_loop
    from synapse.skills.builtins.local_executor import execute_local_task
    from synapse.skills.builtins.read_file import ReadFileSkill
    from synapse.skills.builtins.security_audit import execute_security_audit
    from synapse.skills.builtins.workspace_audit import execute_workspace_audit
    from synapse.skills.dynamic.registry import SkillRegistry

    # Initialize determinism components
    seed_manager = DeterministicSeedManager()
    id_generator = DeterministicIDGenerator()

    # LLM
    llm = LiteLLMProvider(
        name="primary",
        model=llm_model,
        api_key=api_key or _os.getenv("OPENAI_API_KEY", ""),
    )

    workspace = Path(workspace_root or _os.getcwd()).expanduser().resolve()

    # Memory
    db = db_path or _os.path.join(_os.path.expanduser("~"), ".synapse", "memory.db")
    if db != ":memory:":
        _os.makedirs(_os.path.dirname(_os.path.abspath(db)), exist_ok=True)
    memory = MemoryStore(db_path=db)
    memory.workspace_root = workspace
    vector = VectorMemoryStore(persist_directory=vector_persist_dir)
    memory.vector_store = vector  # attach semantic store

    from synapse.core.capability_scope import CapabilityToken

    security = SecurityManager()
    for capability in (
        "fs:read",
        "memory:read",
        "memory:write",
        "net:http",
        "code:generate",
    ):
        security.capability_manager.register_token(CapabilityToken(
            scope=capability,
            issued_to="orchestrator",
            issued_by="builtin-bootstrap",
        ))
    checkpoint_mgr = CheckpointManager()

    skill_capability_manager = SkillCapabilityManager()
    for capability in (
        "fs:read",
        "fs:write",
        "memory:read",
        "memory:write",
        "net:http",
        "code:generate",
        "os:process",
    ):
        skill_capability_manager.grant(capability)
    skill_registry = SkillRegistry(capability_manager=skill_capability_manager)
    skill_registry.register_builtin(
        SkillManifest(
            name="read_file",
            description="Read a UTF-8 text file with an explicit fs:read grant",
            required_capabilities=["fs:read"],
            risk_level=1,
            trust_level="verified",
        ),
        ReadFileSkill(workspace_root=workspace),
    )
    skill_registry.register_builtin(
        SkillManifest(
            name="workspace_audit",
            description="Read-only inventory of workspace structure and key project metadata",
            required_capabilities=["fs:read"],
            risk_level=1,
            trust_level="verified",
        ),
        execute_workspace_audit,
    )
    skill_registry.register_builtin(
        SkillManifest(
            name="security_audit",
            description="Read-only static security audit of the workspace",
            required_capabilities=["fs:read"],
            risk_level=1,
            trust_level="verified",
        ),
        execute_security_audit,
    )
    skill_registry.register_builtin(
        SkillManifest(
            name="generic_executor",
            description="Execute ordinary chat/general tasks with the downloaded local model",
            required_capabilities=["memory:read"],
            risk_level=1,
            trust_level="trusted",
        ),
        execute_local_task,
    )
    skill_registry.register_builtin(
        SkillManifest(
            name="external_agent",
            description="Delegate a bounded task to an installed external coding agent CLI (Claude Code or Codex)",
            required_capabilities=["fs:read", "os:process"],
            risk_level=2,
            trust_level="trusted",
        ),
        execute_external_agent,
    )
    skill_registry.register_builtin(
        SkillManifest(
            name="learning_loop",
            description="Run the chat-driven learning loop: generate verified pairs, snapshot, LoRA-train while holdout improves",
            required_capabilities=["memory:read", "fs:read", "fs:write"],
            risk_level=3,
            trust_level="trusted",
        ),
        execute_learning_loop,
    )

    # Supported local skills have deterministic fallback plans. An external
    # LLM is used only when its credential has actually been configured.
    planner_llm = llm if (api_key or _os.getenv("OPENAI_API_KEY")) else None
    planner = PlannerAgent(
        llm_provider=planner_llm,
        memory_store=memory,
        skill_registry=skill_registry,
    )
    critic = CriticAgent(llm_provider=planner_llm)
    developer = DeveloperAgent(llm_provider=planner_llm)
    learning = LearningEngine(
        memory=memory,
        developer_agent=developer,
        critic_agent=critic,
        vector_store=vector,
    )

    return Orchestrator(
        seed_manager=seed_manager,
        id_generator=id_generator,
        security_manager=security,
        memory_store=memory,
        checkpoint_manager=checkpoint_mgr,
        planner=planner,
        critic=critic,
        learning_engine=learning,
        skill_registry=skill_registry,
    )
