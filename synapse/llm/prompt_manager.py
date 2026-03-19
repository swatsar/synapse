"""Prompt Version Management System.

Protocol Version: 1.0
Specification: 3.1

Adapted from Agent Zero prompt management + Anthropic prompt engineering patterns
(AGENT_ZERO_INTEGRATION.md §5, ANTHROPIC_PATTERNS_INTEGRATION.md §3).

Features:
- Versioned prompt templates (semantic versioning)
- Variable interpolation with validation
- A/B testing support
- Audit trail per prompt version
- Rollback to previous version
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """A versioned prompt template."""
    version: str               # e.g. "1.0.0"
    template: str              # The prompt text with {variable} placeholders
    variables: List[str] = field(default_factory=list)  # Expected variable names
    description: str = ""
    author: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True
    performance_score: float = 0.0  # 0.0–1.0, updated by LearningEngine
    protocol_version: str = PROTOCOL_VERSION

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]

    def render(self, **kwargs) -> str:
        """Render the prompt with given variables."""
        missing = [v for v in self.variables if v not in kwargs]
        if missing:
            raise ValueError(f"Missing prompt variables: {missing}")
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Template variable error: {e}") from e

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "hash": self.hash,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "performance_score": self.performance_score,
            "variables": self.variables,
            "protocol_version": self.protocol_version,
        }


class PromptManager:
    """Manages versioned prompt templates for all agents.

    Adapted from Agent Zero prompt patterns (AGENT_ZERO_INTEGRATION.md §5.1).
    Adds: version history, performance tracking, rollback, audit logging.
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(self):
        # prompt_name → list[PromptVersion] (newest last)
        self._prompts: Dict[str, List[PromptVersion]] = {}
        self._load_defaults()
        audit(event="prompt_manager_initialized", protocol_version=PROTOCOL_VERSION)

    def _load_defaults(self) -> None:
        """Register built-in prompt templates."""
        defaults = {
            "planner_system": PromptVersion(
                version="1.0.0",
                template=(
                    "You are a Planner Agent for Synapse v3.1.\n"
                    "Task: {task}\n"
                    "Available skills: {skills}\n"
                    "Memory context: {memory}\n"
                    "Decompose the task into concrete steps. Return valid JSON."
                ),
                variables=["task", "skills", "memory"],
                description="System prompt for PlannerAgent task decomposition",
            ),
            "critic_eval": PromptVersion(
                version="1.0.0",
                template=(
                    "Evaluate this execution result.\n"
                    "Task: {task}\nStatus: {status}\nOutput: {output}\nError: {error}\n"
                    "Return JSON: {{success, score, feedback, recommendations, knowledge_gaps, should_create_skill, suggested_skill_task}}"
                ),
                variables=["task", "status", "output", "error"],
                description="Evaluation prompt for CriticAgent",
            ),
            "developer_codegen": PromptVersion(
                version="1.0.0",
                template=(
                    "Generate ONLY the body of execute() for a Python BaseSkill subclass.\n"
                    "Task: {task}\nSkill name: {skill_name}\n"
                    "RULES: No os/sys/subprocess imports. Store result in variable `result`. Return only code."
                ),
                variables=["task", "skill_name"],
                description="Code generation prompt for DeveloperAgent",
            ),
            "guardian_assessment": PromptVersion(
                version="1.0.0",
                template=(
                    "Assess security risk for this plan.\n"
                    "Plan goal: {goal}\nRequired capabilities: {capabilities}\nRisk level: {risk_level}\n"
                    "Should this require human approval? Return JSON: {{approved, reason, risk_assessment}}"
                ),
                variables=["goal", "capabilities", "risk_level"],
                description="Security assessment prompt for GuardianAgent",
            ),
        }
        for name, pv in defaults.items():
            self._prompts[name] = [pv]

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def register(self, name: str, version: PromptVersion) -> None:
        """Register a new (or updated) prompt version."""
        if name in self._prompts:
            # Deactivate previous active version
            for pv in self._prompts[name]:
                pv.is_active = False
            self._prompts[name].append(version)
        else:
            self._prompts[name] = [version]
        version.is_active = True
        audit(
            event="prompt_registered",
            name=name,
            version=version.version,
            hash=version.hash,
            protocol_version=PROTOCOL_VERSION,
        )

    def get_active(self, name: str) -> Optional[PromptVersion]:
        """Return the currently active prompt version."""
        versions = self._prompts.get(name, [])
        for pv in reversed(versions):
            if pv.is_active:
                return pv
        return versions[-1] if versions else None

    def render(self, name: str, **kwargs) -> str:
        """Render the active prompt for `name` with given variables."""
        pv = self.get_active(name)
        if not pv:
            raise KeyError(f"Prompt not found: {name!r}")
        rendered = pv.render(**kwargs)
        audit(
            event="prompt_rendered",
            name=name,
            version=pv.version,
            protocol_version=PROTOCOL_VERSION,
        )
        return rendered

    def rollback(self, name: str) -> Optional[PromptVersion]:
        """Rollback to the previous version."""
        versions = self._prompts.get(name, [])
        if len(versions) < 2:
            logger.warning("No previous version to rollback to for prompt: %s", name)
            return None
        # Deactivate current
        for pv in versions:
            pv.is_active = False
        previous = versions[-2]
        previous.is_active = True
        audit(event="prompt_rollback", name=name, version=previous.version, protocol_version=PROTOCOL_VERSION)
        return previous

    def update_performance(self, name: str, score: float) -> None:
        """Update performance score for the active prompt (used by LearningEngine)."""
        pv = self.get_active(name)
        if pv:
            pv.performance_score = max(0.0, min(1.0, score))
            audit(event="prompt_score_updated", name=name, score=pv.performance_score, protocol_version=PROTOCOL_VERSION)

    def list_prompts(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all prompt names and their version history."""
        return {name: [pv.to_dict() for pv in versions] for name, versions in self._prompts.items()}

    def list_names(self) -> List[str]:
        return list(self._prompts.keys())
