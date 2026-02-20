"""Skills Base Module.

Provides base classes and types for skills with audit logging.
Spec v3.1 compliant.
"""
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Re-export RuntimeIsolationType from core
from synapse.core.isolation_policy import RuntimeIsolationType
from synapse.observability.logger import audit


class SkillTrustLevel(str):
    """Trust levels for skills."""
    TRUSTED = "trusted"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class BaseSkill(ABC):
    """Abstract base class for all skills with audit logging."""

    protocol_version: str = "1.0"

    def __init__(self, manifest=None):
        self.protocol_version = "1.0"
        self.manifest = manifest

        # Audit: skill initialized
        skill_name = getattr(manifest, 'name', self.__class__.__name__) if manifest else self.__class__.__name__
        audit(
            event="skill_initialized",
            skill_name=skill_name,
            protocol_version=self.protocol_version
        )

    @abstractmethod
    async def execute(self, context, **kwargs) -> Dict[str, Any]:
        """Execute the skill with audit logging.

        Args:
            context: ExecutionContext
            **kwargs: Skill-specific arguments

        Returns:
            Execution result
        """
        pass

    async def _execute_with_audit(self, context, **kwargs) -> Dict[str, Any]:
        """Execute skill with automatic audit logging.

        This method wraps execute() with audit logging.

        Args:
            context: ExecutionContext
            **kwargs: Skill-specific arguments

        Returns:
            Execution result
        """
        skill_name = self.__class__.__name__
        trace_id = getattr(context, 'trace_id', 'unknown') if context else 'unknown'

        # Audit: skill execution started
        audit(
            event="skill_execution_started",
            skill_name=skill_name,
            trace_id=trace_id,
            kwargs_keys=list(kwargs.keys()),
            protocol_version=self.protocol_version
        )

        try:
            result = await self.execute(context, **kwargs)

            # Audit: skill execution completed
            audit(
                event="skill_execution_completed",
                skill_name=skill_name,
                trace_id=trace_id,
                success=result.get('success', True) if isinstance(result, dict) else True,
                protocol_version=self.protocol_version
            )

            return result

        except Exception as e:
            # Audit: skill execution failed
            audit(
                event="skill_execution_failed",
                skill_name=skill_name,
                trace_id=trace_id,
                error_type=type(e).__name__,
                error_message=str(e)[:200],
                protocol_version=self.protocol_version
            )
            raise

    def get_required_capabilities(self) -> list:
        """Get required capabilities.

        Returns:
            List of required capabilities
        """
        if self.manifest:
            return getattr(self.manifest, "required_capabilities", [])
        return []
