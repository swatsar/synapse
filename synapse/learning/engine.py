"""Learning Engine — metacognition and continuous improvement.

Protocol Version: 1.0
Specification: 3.1

Implements the full learning pipeline:
1. evaluate() — classify execution result (success/failure)
2. feedback() — store to semantic memory with rich metadata
3. process() — end-to-end: evaluate + feedback + metacognition
4. analyze_patterns() — detect recurring failures → trigger CreateSkill
5. optimize_prompts() — detect low-performance agents → suggest prompt improvements
6. create_knowledge() — store structured knowledge for semantic retrieval

Metacognition:
- Tracks success_rate per skill over sliding 7-day window
- If success_rate < 80% → marks skill for re-generation (DEPRECATED)
- If same task fails 3+ times → triggers CreateSkill pipeline
- If capability denied 3+ times → triggers CreateKnowledge
"""
import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from synapse.memory.store import MemoryStore
from synapse.observability.logger import audit, record_metric, trace

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)

SUCCESS = "success"
FAILURE = "failure"

# Thresholds from specification
SUCCESS_RATE_THRESHOLD = 0.80          # < 80% → skill deprecated
FAILURE_TRIGGER_COUNT = 3              # N failures → create_skill
CAPABILITY_DENIED_TRIGGER = 3          # N denied → create_knowledge
SLIDING_WINDOW_DAYS = 7


class LearningEngine:
    """Core learning engine implementing metacognition loop.

    Stores all experiences in MemoryStore and semantic VectorStore.
    Detects patterns → drives DeveloperAgent/CreateKnowledge.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        memory: MemoryStore,
        developer_agent: Any = None,
        critic_agent: Any = None,
        vector_store: Any = None,
    ):
        self.memory = memory
        self.developer = developer_agent
        self.critic = critic_agent
        self.vector_store = vector_store

        # In-memory tracking (persisted to memory store periodically)
        self._skill_results: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
        # skill_name → [(timestamp, success)]
        self._failure_tasks: Dict[str, int] = defaultdict(int)
        # task_hash → failure_count
        self._capability_denials: Dict[str, int] = defaultdict(int)
        # capability → denial_count

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    async def evaluate(self, result: Any) -> str:
        """Classify execution result as SUCCESS or FAILURE."""
        async with trace("learning_evaluate"):
            if isinstance(result, dict):
                status = result.get("status", "")
                has_error = bool(result.get("error"))
                success_flag = result.get("success")
                if success_flag is True:
                    classification = SUCCESS
                elif success_flag is False:
                    classification = FAILURE
                elif status == "completed" and not has_error:
                    classification = SUCCESS
                elif status in ("error", "failed", "blocked"):
                    classification = FAILURE
                else:
                    classification = SUCCESS if not has_error else FAILURE
            else:
                classification = SUCCESS if result else FAILURE

            record_metric("learning_evaluations")
            return classification

    async def feedback(self, result: Any, classification: str) -> None:
        """Store experience in MemoryStore + VectorStore."""
        async with trace("learning_feedback"):
            ts = datetime.now(timezone.utc).isoformat()
            entry = {
                "classification": classification,
                "timestamp": ts,
                "result_summary": self._summarize(result),
                "protocol_version": PROTOCOL_VERSION,
            }

            # Episodic memory
            key = f"experience:{ts}"
            await self.memory.add_episodic(key, entry)

            # Semantic memory for retrieval
            if self.vector_store:
                text = f"{classification}: {entry['result_summary']}"
                await self.vector_store.add_document(
                    text=text,
                    metadata={"classification": classification, "timestamp": ts},
                )

            record_metric("learning_feedbacks")

    async def process(self, result: Any, task: str = "", skill_name: str = "") -> None:
        """Full pipeline: evaluate → feedback → metacognition."""
        classification = await self.evaluate(result)
        await self.feedback(result, classification)
        await self._metacognition(result, classification, task, skill_name)

    # ------------------------------------------------------------------
    # Metacognition
    # ------------------------------------------------------------------

    async def _metacognition(
        self, result: Any, classification: str, task: str, skill_name: str
    ) -> None:
        """Analyse patterns; trigger CreateSkill or CreateKnowledge."""
        async with trace("metacognition"):
            now = time.time()

            # Track per-skill performance
            if skill_name:
                self._skill_results[skill_name].append((now, classification == SUCCESS))
                self._prune_old_records(skill_name)
                await self._check_skill_deprecation(skill_name)

            # Track per-task failures
            if task and classification == FAILURE:
                task_hash = str(hash(task[:120]) % 10**8)
                self._failure_tasks[task_hash] += 1
                count = self._failure_tasks[task_hash]
                audit(
                    event="task_failure_tracked",
                    task_preview=task[:60],
                    failure_count=count,
                    protocol_version=PROTOCOL_VERSION,
                )
                if count >= FAILURE_TRIGGER_COUNT:
                    await self._trigger_create_skill(task)
                    self._failure_tasks[task_hash] = 0  # reset after trigger

            # Track capability denials
            if isinstance(result, dict):
                blocked = result.get("blocked_capabilities", [])
                for cap in blocked:
                    self._capability_denials[cap] += 1
                    if self._capability_denials[cap] >= CAPABILITY_DENIED_TRIGGER:
                        await self._trigger_create_knowledge(cap)
                        self._capability_denials[cap] = 0

    async def _check_skill_deprecation(self, skill_name: str) -> None:
        """Deprecate skill if success_rate drops below threshold."""
        records = self._skill_results[skill_name]
        if len(records) < 5:  # Need minimum sample
            return
        recent = [s for _, s in records]
        rate = sum(recent) / len(recent)
        if rate < SUCCESS_RATE_THRESHOLD:
            audit(
                event="skill_low_success_rate",
                skill=skill_name,
                success_rate=round(rate, 3),
                threshold=SUCCESS_RATE_THRESHOLD,
                action="marking_deprecated",
                protocol_version=PROTOCOL_VERSION,
            )
            # Store deprecation marker in memory
            await self.memory.add_long_term(
                f"deprecated_skill:{skill_name}",
                {
                    "skill": skill_name,
                    "success_rate": rate,
                    "deprecated_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "success_rate_below_threshold",
                },
            )

    async def _trigger_create_skill(self, task: str) -> None:
        """Trigger DeveloperAgent to create a new skill for a recurring failure."""
        audit(
            event="create_skill_triggered",
            task_preview=task[:80],
            reason=f"Failed {FAILURE_TRIGGER_COUNT}+ times",
            protocol_version=PROTOCOL_VERSION,
        )
        if self.developer:
            try:
                result = await self.developer.generate_skill(task_description=task)
                skill = result.get("skill")
                if skill:
                    audit(
                        event="skill_generated_from_learning",
                        skill_id=skill.skill_id,
                        name=skill.name,
                        protocol_version=PROTOCOL_VERSION,
                    )
            except Exception as e:
                logger.warning("create_skill_triggered failed: %s", e)

    async def _trigger_create_knowledge(self, capability: str) -> None:
        """Store structured knowledge about a frequently-denied capability."""
        audit(
            event="create_knowledge_triggered",
            capability=capability,
            denial_count=CAPABILITY_DENIED_TRIGGER,
            protocol_version=PROTOCOL_VERSION,
        )
        knowledge_text = (
            f"Capability '{capability}' is frequently denied. "
            f"Agent should request elevated access or find alternative approach "
            f"that does not require '{capability}'."
        )
        await self.memory.add_long_term(
            f"knowledge:cap_denied:{capability}",
            {
                "type": "knowledge",
                "capability": capability,
                "guidance": knowledge_text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if self.vector_store:
            await self.vector_store.add_document(
                text=knowledge_text,
                metadata={"type": "capability_knowledge", "capability": capability},
            )

    # ------------------------------------------------------------------
    # Metacognition: pattern analysis
    # ------------------------------------------------------------------

    async def analyze_patterns(self) -> Dict[str, Any]:
        """Analyse stored experiences; return summary of insights."""
        async with trace("analyze_patterns"):
            insights: Dict[str, Any] = {
                "low_performing_skills": [],
                "frequent_failure_tasks": [],
                "capability_bottlenecks": [],
                "protocol_version": PROTOCOL_VERSION,
            }

            for skill, records in self._skill_results.items():
                if len(records) >= 3:
                    rate = sum(s for _, s in records) / len(records)
                    if rate < SUCCESS_RATE_THRESHOLD:
                        insights["low_performing_skills"].append({
                            "skill": skill,
                            "success_rate": round(rate, 3),
                            "sample_size": len(records),
                        })

            for task_hash, count in self._failure_tasks.items():
                if count >= FAILURE_TRIGGER_COUNT:
                    insights["frequent_failure_tasks"].append({
                        "task_hash": task_hash,
                        "failure_count": count,
                    })

            for cap, count in self._capability_denials.items():
                if count >= CAPABILITY_DENIED_TRIGGER:
                    insights["capability_bottlenecks"].append({
                        "capability": cap,
                        "denial_count": count,
                    })

            audit(
                event="pattern_analysis_completed",
                low_performing=len(insights["low_performing_skills"]),
                bottlenecks=len(insights["capability_bottlenecks"]),
                protocol_version=PROTOCOL_VERSION,
            )
            return insights

    async def optimize_prompts(self, agent_name: str) -> Dict[str, Any]:
        """Suggest prompt improvements for under-performing agents.

        In production this would use LLM to generate improved system prompts.
        """
        audit(
            event="optimize_prompts_started",
            agent=agent_name,
            protocol_version=PROTOCOL_VERSION,
        )
        # Retrieve recent failures for this agent from memory
        failures = await self.memory.search(f"failure {agent_name}")
        suggestion = (
            f"Agent '{agent_name}' prompt optimization: "
            f"Found {len(failures)} recent failure records. "
            f"Consider adding more explicit output format instructions "
            f"and error handling guidance to system prompt."
        )
        return {
            "agent": agent_name,
            "suggestion": suggestion,
            "failure_sample_count": len(failures),
            "protocol_version": PROTOCOL_VERSION,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _summarize(self, result: Any) -> str:
        """Produce a short text summary of a result."""
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            error = result.get("error", "")
            return f"status={status} error={str(error)[:80]}" if error else f"status={status}"
        return str(result)[:120]

    def _prune_old_records(self, skill_name: str) -> None:
        """Remove records older than SLIDING_WINDOW_DAYS."""
        cutoff = time.time() - SLIDING_WINDOW_DAYS * 86400
        self._skill_results[skill_name] = [
            (ts, s) for ts, s in self._skill_results[skill_name] if ts > cutoff
        ]
