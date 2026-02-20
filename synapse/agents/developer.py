"""Developer Agent for autonomous skill code generation.

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
class GeneratedSkill:
    """Generated skill code and metadata."""
    code: str
    name: str
    version: str
    protocol_version: str = "1.0"


class DeveloperAgent:
    """Agent that generates skill code with audit logging.

    Responsibilities:
    - Generate skill code from specifications
    - Register skills with registry
    - Check policy before registration
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        llm_provider: Any = None,
        skill_registry: Any = None,
        policy_engine: Any = None
    ):
        self.llm_provider = llm_provider
        self.skill_registry = skill_registry
        self.policy_engine = policy_engine

        # Audit: developer agent initialized
        audit(
            event="developer_agent_initialized",
            has_llm_provider=llm_provider is not None,
            has_skill_registry=skill_registry is not None,
            protocol_version=self.protocol_version
        )

    async def generate_skill(
        self,
        task_description: str,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate skill code from task description with audit logging.

        Args:
            task_description: Description of the task
            seed: Optional seed for deterministic output

        Returns:
            Generated skill with code and metadata
        """
        # Audit: skill generation started
        audit(
            event="skill_generation_started",
            task_description_length=len(task_description),
            seed=seed,
            protocol_version=self.protocol_version
        )

        # Create prompt
        prompt = self.create_prompt(task_description, seed)

        # Generate code (mock implementation)
        if self.llm_provider:
            response = await self.llm_provider.generate(prompt)
            result = {
                "code": response.get("code", "class Skill:\n    pass"),
                "protocol_version": self.protocol_version
            }

            # Audit: skill generation completed with LLM
            audit(
                event="skill_generation_completed",
                source="llm_provider",
                code_length=len(result["code"]),
                protocol_version=self.protocol_version
            )

            return result

        # Deterministic mock response
        hash_input = f"{task_description}:{seed or 0}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()

        result = {
            "code": f"class GeneratedSkill{hash_value[:8]}:\n    def execute(self): pass",
            "protocol_version": self.protocol_version
        }

        # Audit: skill generation completed with mock
        audit(
            event="skill_generation_completed",
            source="mock",
            code_length=len(result["code"]),
            protocol_version=self.protocol_version
        )

        return result

    def create_prompt(
        self,
        task_description: str,
        seed: Optional[int] = None
    ) -> str:
        """Create prompt for skill generation.

        Args:
            task_description: Description of the task
            seed: Optional seed for deterministic output

        Returns:
            Prompt string
        """
        return f"""Generate a Python skill class for the following task:

Task: {task_description}

Requirements:
1. Follow protocol_version="1.0" conventions
2. Include type hints
3. Include docstrings
4. Handle errors gracefully

Seed: {seed or 0}
"""

    async def create_and_register(
        self,
        task_description: str,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create and register a skill with audit logging.

        Args:
            task_description: Description of the task
            seed: Optional seed for deterministic output

        Returns:
            Registration result
        """
        # Audit: registration started
        audit(
            event="skill_registration_started",
            task_description=task_description[:100],
            protocol_version=self.protocol_version
        )

        # Generate skill
        skill = await self.generate_skill(task_description, seed)

        # Check policy
        if self.policy_engine:
            policy_result = await self.policy_engine.check(skill)
            if not policy_result.get("approved", True):
                # Audit: registration denied by policy
                audit(
                    event="skill_registration_denied",
                    reason="policy_violation",
                    protocol_version=self.protocol_version
                )
                return {
                    "status": "denied",
                    "reason": "Policy violation",
                    "protocol_version": self.protocol_version
                }

        # Register skill
        if self.skill_registry:
            registration = await self.skill_registry.register(skill)

            # Audit: registration completed
            audit(
                event="skill_registration_completed",
                skill_name=skill.get("name", "unknown"),
                protocol_version=self.protocol_version
            )

            return {
                "status": "registered",
                "skill": skill,
                "registration": registration,
                "protocol_version": self.protocol_version
            }

        # Audit: registration completed (no registry)
        audit(
            event="skill_registration_completed",
            skill_name="generated_skill",
            registry="none",
            protocol_version=self.protocol_version
        )

        return {
            "status": "generated",
            "skill": skill,
            "protocol_version": self.protocol_version
        }
