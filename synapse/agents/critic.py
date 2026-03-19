"""Critic Agent — evaluates skill results and drives learning.

Protocol Version: 1.0
Specification: 3.1

Responsibilities:
- Evaluate skill/action execution outcomes via structured LLM analysis
- Produce scored EvaluationResult with actionable feedback
- Detect knowledge gaps → trigger CreateSkill / CreateKnowledge
- Emit full audit trail for every evaluation
"""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of a Critic evaluation."""
    success: bool
    score: float                        # 0.0 – 1.0
    feedback: str
    recommendations: List[str] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)
    should_create_skill: bool = False
    suggested_skill_task: str = ""
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "score": self.score,
            "feedback": self.feedback,
            "recommendations": self.recommendations,
            "knowledge_gaps": self.knowledge_gaps,
            "should_create_skill": self.should_create_skill,
            "suggested_skill_task": self.suggested_skill_task,
            "protocol_version": self.protocol_version,
        }


EVAL_PROMPT = """You are a Critic Agent evaluating the result of an autonomous agent action.

TASK that was attempted:
{task}

EXECUTION RESULT:
Status: {status}
Output: {output}
Error: {error}

Evaluate strictly and return a JSON object with these fields:
- success (bool): was the task accomplished?
- score (float 0.0-1.0): quality of the result
- feedback (string): clear explanation of what went right/wrong
- recommendations (list of strings): concrete steps to improve
- knowledge_gaps (list of strings): missing capabilities or knowledge
- should_create_skill (bool): should a new skill be created to handle this better?
- suggested_skill_task (string): if should_create_skill, describe what the skill should do

Return ONLY valid JSON, no markdown, no explanations."""


class CriticAgent:
    """Evaluates execution outcomes and provides structured feedback.

    Uses LLM for deep analysis when available.
    Falls back to deterministic heuristics.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        llm_provider: Any = None,
        audit_logger: Any = None,
        success_threshold: float = 0.7,
    ):
        self.llm_provider = llm_provider
        self.audit_logger = audit_logger
        self.success_threshold = success_threshold
        audit(
            event="critic_agent_initialized",
            has_llm=llm_provider is not None,
            protocol_version=self.protocol_version,
        )

    async def evaluate(
        self,
        execution_result: Dict[str, Any],
        task: str = "",
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Evaluate an execution result.

        Args:
            execution_result: Dict with 'status', 'result', 'error'
            task: Original task description
            seed: Optional determinism seed

        Returns:
            Dict wrapping EvaluationResult
        """
        audit(
            event="evaluation_started",
            status=execution_result.get("status"),
            task_preview=task[:80],
            seed=seed,
            protocol_version=self.protocol_version,
        )

        # Try LLM evaluation first
        result = await self._evaluate_with_llm(execution_result, task)
        if result is None:
            result = self._evaluate_heuristic(execution_result, task)

        audit(
            event="evaluation_completed",
            success=result.success,
            score=result.score,
            should_create_skill=result.should_create_skill,
            gaps_count=len(result.knowledge_gaps),
            protocol_version=self.protocol_version,
        )

        return result.to_dict()

    async def _evaluate_with_llm(
        self, result: Dict, task: str
    ) -> Optional[EvaluationResult]:
        """Use LLM for structured evaluation."""
        if not self.llm_provider:
            return None
        try:
            import json as _json
            status = result.get("status", "unknown")
            output = str(result.get("result", ""))[:500]
            error = str(result.get("error", ""))[:300]

            prompt = EVAL_PROMPT.format(
                task=task[:300],
                status=status,
                output=output,
                error=error,
            )
            response = await self.llm_provider.generate(prompt)
            content = response.get("content", "{}")
            # Strip markdown fences
            content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = _json.loads(content)

            return EvaluationResult(
                success=bool(data.get("success", False)),
                score=float(data.get("score", 0.5)),
                feedback=str(data.get("feedback", "")),
                recommendations=list(data.get("recommendations", [])),
                knowledge_gaps=list(data.get("knowledge_gaps", [])),
                should_create_skill=bool(data.get("should_create_skill", False)),
                suggested_skill_task=str(data.get("suggested_skill_task", "")),
            )
        except Exception as e:
            logger.warning("LLM evaluation failed: %s", e)
            return None

    def _evaluate_heuristic(
        self, result: Dict, task: str
    ) -> EvaluationResult:
        """Deterministic heuristic evaluation when LLM unavailable."""
        status = result.get("status", "unknown")
        has_error = bool(result.get("error"))
        has_result = result.get("result") is not None

        # Score computation
        if status == "completed" and not has_error and has_result:
            score = 1.0
            success = True
            feedback = "Task completed successfully with result."
            recommendations = []
            gaps: List[str] = []
            should_create = False
            suggested = ""
        elif status == "completed" and not has_result:
            score = 0.6
            success = True
            feedback = "Task completed but produced no output. Consider improving result handling."
            recommendations = ["Ensure skill returns meaningful result"]
            gaps = []
            should_create = False
            suggested = ""
        elif has_error:
            score = 0.1
            success = False
            error_msg = str(result.get("error", ""))
            feedback = f"Task failed with error: {error_msg[:200]}"
            recommendations = ["Fix error handling", "Add retry logic", "Verify input parameters"]
            # Detect knowledge gap patterns
            gaps = []
            if "not found" in error_msg.lower() or "no module" in error_msg.lower():
                gaps.append(f"Missing dependency or module for task: {task[:60]}")
            if "permission" in error_msg.lower():
                gaps.append("Missing capability/permission for this operation")
            should_create = len(gaps) > 0
            suggested = f"Create skill to handle: {task[:80]}" if should_create else ""
        else:
            score = 0.3
            success = False
            feedback = f"Task ended in unexpected state: {status}"
            recommendations = ["Investigate skill execution flow", "Add better status reporting"]
            gaps = []
            should_create = False
            suggested = ""

        return EvaluationResult(
            success=success,
            score=score,
            feedback=feedback,
            recommendations=recommendations,
            knowledge_gaps=gaps,
            should_create_skill=should_create,
            suggested_skill_task=suggested,
        )

    def create_evaluation_prompt(
        self,
        execution_result: Dict[str, Any],
        seed: Optional[int] = None,
    ) -> str:
        """Public method for tests."""
        return EVAL_PROMPT.format(
            task="(unknown)",
            status=execution_result.get("status", "unknown"),
            output=str(execution_result.get("result", ""))[:200],
            error=str(execution_result.get("error", ""))[:100],
        )
