"""Critic Agent for skill execution evaluation.

Implements SYSTEM_SPEC_v3.1 Phase 9 - Autonomous Skill Evolution.
With comprehensive audit logging.
"""
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


@dataclass
class EvaluationResult:
    """Result of skill evaluation."""
    success: bool
    score: float
    feedback: str
    recommendations: list
    protocol_version: str = "1.0"


class CriticAgent:
    """Agent that evaluates skill execution results with audit logging.

    Responsibilities:
    - Evaluate skill execution outcomes
    - Provide actionable feedback
    - Log evaluations for audit
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        llm_provider: Any = None,
        audit_logger: Any = None
    ):
        self.llm_provider = llm_provider
        self.audit_logger = audit_logger

        # Audit: critic agent initialized
        audit(
            event="critic_agent_initialized",
            has_llm_provider=llm_provider is not None,
            has_audit_logger=audit_logger is not None,
            protocol_version=self.protocol_version
        )

    async def evaluate(
        self,
        execution_result: Dict[str, Any],
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Evaluate skill execution result with audit logging.

        Args:
            execution_result: Result of skill execution
            seed: Optional seed for deterministic output

        Returns:
            Evaluation with success, score, and feedback
        """
        # Audit: evaluation started
        audit(
            event="evaluation_started",
            execution_status=execution_result.get("status", "unknown"),
            seed=seed,
            protocol_version=self.protocol_version
        )

        # Create evaluation prompt
        prompt = self.create_evaluation_prompt(execution_result, seed)

        # Generate evaluation (mock implementation)
        if self.llm_provider:
            response = await self.llm_provider.generate(prompt)
            result = {
                "success": response.get("evaluation", {}).get("success", True),
                "score": response.get("evaluation", {}).get("score", 0.9),
                "feedback": response.get("evaluation", {}).get("feedback", "Good"),
                "protocol_version": self.protocol_version
            }

            # Audit: evaluation completed with LLM
            audit(
                event="evaluation_completed",
                source="llm_provider",
                success=result["success"],
                score=result["score"],
                protocol_version=self.protocol_version
            )

            return result

        # Deterministic evaluation based on execution status
        status = execution_result.get("status", "unknown")

        # Simple heuristic: completed = success
        success = status == "completed"
        score = 1.0 if success else 0.0
        feedback = "Execution completed successfully" if success else "Execution failed"

        result = {
            "success": success,
            "score": score,
            "feedback": feedback,
            "recommendations": [],
            "protocol_version": self.protocol_version
        }

        # Audit: evaluation completed with heuristic
        audit(
            event="evaluation_completed",
            source="heuristic",
            success=success,
            score=score,
            protocol_version=self.protocol_version
        )

        return result

    def create_evaluation_prompt(
        self,
        execution_result: Dict[str, Any],
        seed: Optional[int] = None
    ) -> str:
        """Create prompt for evaluation.

        Args:
            execution_result: Result of skill execution
            seed: Optional seed for deterministic output

        Returns:
            Prompt string
        """
        return f"""Evaluate the following skill execution result:

Execution Result:
{execution_result}

Provide evaluation with:
1. success: bool
2. score: float (0.0 to 1.0)
3. feedback: str
4. recommendations: list

Seed: {seed or 0}
Protocol Version: {self.protocol_version}
"""

    async def evaluate_and_learn(
        self,
        execution_result: Dict[str, Any],
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Evaluate and store learning with audit logging.

        Args:
            execution_result: Result of skill execution
            seed: Optional seed for deterministic output

        Returns:
            Evaluation with learning stored
        """
        # Audit: learning evaluation started
        audit(
            event="learning_evaluation_started",
            protocol_version=self.protocol_version
        )

        # Evaluate
        evaluation = await self.evaluate(execution_result, seed)

        # Store learning (mock)
        learning_stored = True

        # Audit: learning evaluation completed
        audit(
            event="learning_evaluation_completed",
            success=evaluation["success"],
            learning_stored=learning_stored,
            protocol_version=self.protocol_version
        )

        return {
            **evaluation,
            "learning_stored": learning_stored
        }
