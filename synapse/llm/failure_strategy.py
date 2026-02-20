"""LLM Failure Strategy for fallback switching.

Implements SYSTEM_SPEC_v3.1 - LLM Failure Strategy.
With comprehensive audit logging.
"""
from typing import Dict, List, Optional
from enum import IntEnum
from pydantic import BaseModel

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


class LLMPriority(IntEnum):
    """Priority levels for LLM models."""
    PRIMARY = 1
    FALLBACK_1 = 2
    FALLBACK_2 = 3
    SAFE = 4


class ModelConfig(BaseModel):
    """Configuration for an LLM model."""
    provider: str
    model: str
    priority: LLMPriority
    is_active: bool = True
    failure_count: int = 0
    protocol_version: str = "1.0"


class LLMFailureStrategy:
    """Strategy for handling LLM failures with audit logging."""

    MAX_FAILURES_BEFORE_FAILOVER = 3

    def __init__(self, models: List[ModelConfig], audit_logger=None):
        self.models = sorted(models, key=lambda m: m.priority.value)
        self.audit_logger = audit_logger
        self.current_index = 0

        # Audit: failure strategy initialized
        audit(
            event="llm_failure_strategy_initialized",
            models_count=len(models),
            protocol_version=PROTOCOL_VERSION
        )

    async def record_failure(self, model_name: str, error: str):
        """Record a model failure with audit logging.

        Args:
            model_name: Name of the failed model
            error: Error message
        """
        for model in self.models:
            if model.model == model_name:
                model.failure_count += 1

                # Audit: model failure recorded
                audit(
                    event="llm_model_failure",
                    model=model_name,
                    error=error[:200],
                    failure_count=model.failure_count,
                    protocol_version=PROTOCOL_VERSION
                )

                # Switch to fallback after max failures
                if model.failure_count >= self.MAX_FAILURES_BEFORE_FAILOVER:
                    model.is_active = False
                    await self._switch_to_fallback(model_name)
                break

    async def get_available_model(self) -> Optional[ModelConfig]:
        """Get the best available model with audit logging."""
        for model in self.models:
            if model.is_active:
                # Audit: model selected
                audit(
                    event="llm_model_selected",
                    model=model.model,
                    priority=model.priority.value,
                    protocol_version=PROTOCOL_VERSION
                )
                return model

        # Audit: no models available
        audit(
            event="llm_no_models_available",
            protocol_version=PROTOCOL_VERSION
        )

        return None

    async def _switch_to_fallback(self, failed_model: str):
        """Switch to fallback model with audit logging."""
        # Audit: failover triggered
        audit(
            event="llm_failover_triggered",
            failed_model=failed_model,
            protocol_version=PROTOCOL_VERSION
        )

        # Find next available model
        available = await self.get_available_model()
        if available:
            # Audit: failover completed
            audit(
                event="llm_failover_completed",
                failed_model=failed_model,
                new_model=available.model,
                protocol_version=PROTOCOL_VERSION
            )

    async def reset_failure_counts(self):
        """Reset all failure counts with audit logging."""
        for model in self.models:
            model.failure_count = 0
            model.is_active = True

        # Audit: failure counts reset
        audit(
            event="llm_failure_counts_reset",
            models_count=len(self.models),
            protocol_version=PROTOCOL_VERSION
        )

    def get_status(self) -> Dict:
        """Get current status of all models."""
        return {
            "models": [
                {
                    "model": m.model,
                    "priority": m.priority.value,
                    "is_active": m.is_active,
                    "failure_count": m.failure_count
                }
                for m in self.models
            ],
            "protocol_version": PROTOCOL_VERSION
        }
