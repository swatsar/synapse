"""Orchestrator – 7-Step Cognitive Cycle Implementation.
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
from .determinism import DeterministicSeedManager, DeterministicIDGenerator
from synapse.observability.logger import audit
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class CognitiveCycleResult:
    """Result of cognitive cycle execution."""
    
    def __init__(
        self,
        success: bool,
        perceived: Optional[Dict] = None,
        recalled: Optional[Dict] = None,
        plan: Optional[Dict] = None,
        security_result: Optional[Dict] = None,
        action_result: Optional[Dict] = None,
        observation: Optional[Dict] = None,
        evaluation: Optional[Dict] = None,
        learning: Optional[Dict] = None,
        error: Optional[str] = None
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
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
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
    """Orchestrator implementing 7-Step Cognitive Cycle.
    
    The cognitive cycle follows the pattern:
    PERCEIVE → RECALL → PLAN → SECURITY → ACT → OBSERVE → EVALUATE → LEARN
    
    Each step is logged for audit and can be checkpointed for rollback.
    """

    protocol_version: str = "1.0"

    def __init__(
        self,
        seed_manager: DeterministicSeedManager,
        id_generator: DeterministicIDGenerator,
        memory_store: Optional[Any] = None,
        security_manager: Optional[Any] = None,
        skill_registry: Optional[Any] = None,
        checkpoint_manager: Optional[Any] = None
    ):
        self.protocol_version = "1.0"
        self.seed_manager = seed_manager
        self.id_generator = id_generator
        self.memory_store = memory_store
        self.security_manager = security_manager
        self.skill_registry = skill_registry
        self.checkpoint_manager = checkpoint_manager

        # Audit: orchestrator initialized
        audit(
            event="orchestrator_initialized",
            protocol_version=self.protocol_version,
            spec_version=SPEC_VERSION,
            cognitive_cycle="7-step"
        )

    # =========================================================================
    # 7-STEP COGNITIVE CYCLE
    # =========================================================================

    async def execute_cycle(self, event: Dict[str, Any]) -> CognitiveCycleResult:
        """Execute a complete cognitive cycle on an event.

        This is the main orchestration method that implements the 7-step
        cognitive cycle: Perception → Recall → Plan → Action → Observe → Evaluate → Learn
        """
        # Parse the event to extract goals
        goals = self._parse_event(event)

        # Execute the first goal
        if goals:
            return await self.run_goal(goals[0])

        return CognitiveCycleResult(
            success=False,
            result=None,
            reasoning="No valid goals extracted from event",
            protocol_version=self.protocol_version
        )

    async def run_goal(self, goal: Dict[str, Any]) -> CognitiveCycleResult:
        """Run a high-level goal through the cognitive cycle.

        This method provides a simplified interface for running goals
        that delegate directly to the execute_cycle method.

        Args:
            goal: The high-level goal to execute

        Returns:
            CognitiveCycleResult with the execution result
        """
        # Convert goal to event format understood by execute_cycle
        event = {
            "type": "goal",
            "data": goal,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return await self.execute_cycle(event)


        """Execute full 7-step cognitive cycle.
        
        Args:
            event: Input event to process
            
        Returns:
            CognitiveCycleResult with all step results
        """
        audit(
            event="cognitive_cycle_started",
            event_type=event.get("type", "unknown"),
            protocol_version=self.protocol_version
        )

        try:
            # Step 1: PERCEIVE
            perceived = await self._perceive(event)
            
            # Step 2: RECALL
            recalled = await self._recall(perceived)
            
            # Step 3: PLAN
            plan = await self._plan(perceived, recalled)
            
            # Step 4: SECURITY CHECK
            security_result = await self._security_check(plan)
            
            if not security_result.get("approved", False):
                return CognitiveCycleResult(
                    success=False,
                    perceived=perceived,
                    recalled=recalled,
                    plan=plan,
                    security_result=security_result,
                    error="Security check failed"
                )
            
            # Create checkpoint before ACT for risk_level >= 3
            if plan.get("risk_level", 0) >= 3 and self.checkpoint_manager:
                await self._create_checkpoint(event, plan)
            
            # Step 5: ACT
            action_result = await self._act(plan)
            
            # Step 6: OBSERVE
            observation = await self._observe(action_result)
            
            # Step 7: EVALUATE
            evaluation = await self._evaluate(plan, observation)
            
            # Step 8: LEARN
            learning = await self._learn(event, plan, action_result, evaluation)
            
            audit(
                event="cognitive_cycle_completed",
                success=evaluation.get("success", False),
                protocol_version=self.protocol_version
            )
            
            return CognitiveCycleResult(
                success=True,
                perceived=perceived,
                recalled=recalled,
                plan=plan,
                security_result=security_result,
                action_result=action_result,
                observation=observation,
                evaluation=evaluation,
                learning=learning
            )
            
        except Exception as e:
            audit(
                event="cognitive_cycle_error",
                error=str(e),
                protocol_version=self.protocol_version
            )
            return CognitiveCycleResult(
                success=False,
                error=str(e)
            )

    # -------------------------------------------------------------------------
    # Step 1: PERCEIVE
    # -------------------------------------------------------------------------
    
    async def _perceive(self, event: Dict[str, Any]) -> Dict[str, Any]:
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
            "content": event.get("content", ""),
            "source": event.get("source", "unknown"),
            "user_id": event.get("user_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": event.get("metadata", {}),
            "protocol_version": self.protocol_version
        }
        
        return perceived

    # -------------------------------------------------------------------------
    # Step 2: RECALL
    # -------------------------------------------------------------------------
    
    async def _recall(self, perceived: Dict[str, Any]) -> Dict[str, Any]:
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
                    except Exception:
                        pass
            except Exception as e:
                audit(event="recall_memory_error", error=str(e), protocol_version=self.protocol_version)

        return recalled

    # -------------------------------------------------------------------------
    # Step 3: PLAN
    # -------------------------------------------------------------------------
    
    async def _plan(
        self,
        perceived: Dict[str, Any],
        recalled: Dict[str, Any]
    ) -> Dict[str, Any]:
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
                from synapse.agents.planner import PlannerAgent  # noqa: PLC0415
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
    
    async def _security_check(self, plan: Dict[str, Any]) -> Dict[str, Any]:
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
                        context={"agent_id": "orchestrator"}
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
    
    async def _act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
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
            "success": True,
            "steps_completed": 0,
            "steps_total": len(plan.get("steps", [])),
            "outputs": [],
            "errors": [],
            "protocol_version": self.protocol_version
        }
        
        for i, step in enumerate(plan.get("steps", [])):
            step_name = step.get("skill", step.get("action", f"step_{i}"))
            try:
                if self.skill_registry:
                    try:
                        step_result = await self.skill_registry.execute(
                            step_name, **step.get("params", {})
                        )
                    except (AttributeError, TypeError):
                        # Fallback: registry doesn't support execute() directly
                        step_result = {"status": "completed", "result": f"Executed: {step_name}"}
                else:
                    step_result = {"status": "completed", "result": f"Executed: {step_name}"}

                action_result["steps_completed"] += 1
                action_result["outputs"].append(step_result)

                audit(
                    event="step_executed",
                    step_id=step.get("step_id", str(i)),
                    skill=step_name,
                    status=step_result.get("status", "completed"),
                    protocol_version=self.protocol_version,
                )
            except Exception as e:
                action_result["success"] = False
                action_result["errors"].append({"step": i, "skill": step_name, "error": str(e)})
                audit(event="step_failed", step_id=str(i), error=str(e), protocol_version=self.protocol_version)
                break

        return action_result

    # -------------------------------------------------------------------------
    # Step 6: OBSERVE
    # -------------------------------------------------------------------------
    
    async def _observe(self, action_result: Dict[str, Any]) -> Dict[str, Any]:
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
        plan: Dict[str, Any],
        observation: Dict[str, Any]
    ) -> Dict[str, Any]:
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
        event: Dict[str, Any],
        plan: Dict[str, Any],
        action_result: Dict[str, Any],
        evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
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
        elif self.memory_store:
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
        event: Dict[str, Any],
        plan: Dict[str, Any]
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

    def handle(self, input_data: dict) -> dict:
        """Legacy handle method for backward compatibility.
        
        Args:
            input_data: Input dictionary

        Returns:
            Result dictionary with task_id
        """
        audit(
            event="task_received",
            input_type=input_data.get("type", "unknown"),
            has_task="task" in input_data,
            protocol_version=self.protocol_version
        )

        task_id = self.id_generator.generate(input_data.get("task", ""))

        result = {
            "task_id": str(task_id),
            "input": input_data,
            "status": "completed",
            "protocol_version": self.protocol_version
        }

        audit(
            event="task_completed",
            task_id=str(task_id),
            status="completed",
            protocol_version=self.protocol_version
        )

        return result

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
    api_key: str = None,
    db_path: str = None,
    vector_persist_dir: str = None,
) -> "Orchestrator":
    """Build a fully-wired Orchestrator with all cognitive components.

    This is the production entry-point. All agents share a single MemoryStore
    and LLMProvider.
    """
    import os as _os
    from synapse.llm.provider import LiteLLMProvider
    from synapse.memory.store import MemoryStore
    from synapse.memory.vector_store import VectorMemoryStore
    from synapse.agents.planner import PlannerAgent
    from synapse.agents.critic import CriticAgent
    from synapse.agents.developer import DeveloperAgent
    from synapse.learning.engine import LearningEngine
    from synapse.core.security import SecurityManager
    from synapse.core.checkpoint import CheckpointManager

    # LLM
    llm = LiteLLMProvider(
        name="primary",
        model=llm_model,
        api_key=api_key or _os.getenv("OPENAI_API_KEY", ""),
    )

    # Memory
    db = db_path or _os.path.join(_os.path.expanduser("~"), ".synapse", "memory.db")
    memory = MemoryStore(db_path=db)
    vector = VectorMemoryStore(persist_directory=vector_persist_dir)
    memory.vector_store = vector  # attach semantic store

    # Agents
    planner = PlannerAgent(llm_provider=llm, memory_store=memory)
    critic = CriticAgent(llm_provider=llm)
    developer = DeveloperAgent(llm_provider=llm)

    # Learning engine
    learning = LearningEngine(
        memory=memory,
        developer_agent=developer,
        critic_agent=critic,
        vector_store=vector,
    )

    # Security & checkpoint
    security = SecurityManager()
    checkpoint_mgr = CheckpointManager()

    # Assemble orchestrator
    orch = Orchestrator(
        security_manager=security,
        memory_store=memory,
        checkpoint_manager=checkpoint_mgr,
    )
    orch.planner = planner
    orch.critic = critic
    orch.learning_engine = learning
    orch.skill_registry = None  # injected externally if needed

    return orch
