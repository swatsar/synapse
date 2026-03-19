"""LLM Model Router with Failover and Cost Tracking.

Protocol Version: 1.0
Specification: 3.1

Adapted from LangChain routing patterns (LANGCHAIN_INTEGRATION.md §1.3).
Synapse additions: health checks, cost tracking, capability validation,
protocol versioning, audit logging.
"""
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
logger = logging.getLogger(__name__)

# Cost per 1K tokens (USD) - approximate, update as needed
LLM_COST_PER_1K = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "llama3": {"input": 0.0, "output": 0.0},  # local model
}


class ModelPriority(IntEnum):
    """Priority for failover ordering."""
    PRIMARY = 1
    FALLBACK_1 = 2
    FALLBACK_2 = 3
    SAFE = 4


@dataclass
class ModelConfig:
    """Single LLM model configuration."""
    name: str
    provider: str
    model: str
    priority: ModelPriority = ModelPriority.PRIMARY
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 60
    max_tokens: int = 4096
    is_active: bool = True
    task_types: List[str] = field(default_factory=list)  # "" = all tasks
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class CostRecord:
    """Usage and cost tracking per model."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_calls: int = 0
    failed_calls: int = 0
    total_cost_usd: float = 0.0
    protocol_version: str = PROTOCOL_VERSION

    def add_usage(self, input_tokens: int, output_tokens: int) -> float:
        """Record usage and return cost for this call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_calls += 1
        rates = LLM_COST_PER_1K.get(self.model, {"input": 0.0, "output": 0.0})
        cost = (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]
        self.total_cost_usd += cost
        return cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "protocol_version": self.protocol_version,
        }


class LLMModelRouter:
    """Routes LLM requests with automatic failover and cost tracking.

    Adapted from LangChain routing patterns (LANGCHAIN_INTEGRATION.md §1.3).
    Additions:
    - Automatic failover after 3 consecutive failures
    - Per-model cost tracking (USD)
    - Task-based routing (coding vs chat vs embedding)
    - Health check endpoint
    - Full audit logging
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(self, models: List[ModelConfig], audit_logger: Any = None):
        self.models = sorted(models, key=lambda m: m.priority.value)
        self._audit = audit_logger
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._health: Dict[str, bool] = {m.name: True for m in models}
        self._costs: Dict[str, CostRecord] = {
            m.name: CostRecord(model=m.model) for m in models
        }
        self._last_health_check: float = 0.0

        audit(
            event="llm_router_initialized",
            models=[m.name for m in models],
            protocol_version=PROTOCOL_VERSION,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_model(self, task_type: str = "") -> Optional[ModelConfig]:
        """Return the best available model for the given task type."""
        # Task-specific routing first
        if task_type:
            for m in self.models:
                if (m.is_active and self._health.get(m.name, True)
                        and task_type in m.task_types):
                    return m
        # Priority-ordered fallback
        for m in self.models:
            if m.is_active and self._health.get(m.name, True):
                return m
        return None

    async def record_success(
        self,
        model_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """Record a successful call. Returns cost in USD."""
        self._failure_counts[model_name] = 0
        self._health[model_name] = True
        record = self._costs.get(model_name)
        cost = record.add_usage(input_tokens, output_tokens) if record else 0.0
        audit(
            event="llm_call_success",
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            protocol_version=PROTOCOL_VERSION,
        )
        return cost

    async def record_failure(self, model_name: str, error: str = "") -> None:
        """Record failure. After 3 failures, mark model unhealthy."""
        self._failure_counts[model_name] += 1
        count = self._failure_counts[model_name]
        record = self._costs.get(model_name)
        if record:
            record.failed_calls += 1

        audit(
            event="llm_call_failure",
            model=model_name,
            failure_count=count,
            error=error[:200],
            protocol_version=PROTOCOL_VERSION,
        )

        if count >= 3:
            self._health[model_name] = False
            audit(
                event="llm_model_failover",
                model=model_name,
                failure_count=count,
                protocol_version=PROTOCOL_VERSION,
            )
            logger.warning("Model %s marked unhealthy after %d failures", model_name, count)

    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Return health status of all models."""
        results: Dict[str, Dict[str, Any]] = {}
        for m in self.models:
            results[m.name] = {
                "is_active": m.is_active,
                "is_healthy": self._health.get(m.name, True),
                "failure_count": self._failure_counts.get(m.name, 0),
                "priority": m.priority.value,
                "model": m.model,
                "protocol_version": PROTOCOL_VERSION,
            }
        return results

    def get_cost_summary(self) -> Dict[str, Any]:
        """Return aggregated cost tracking data."""
        records = {name: rec.to_dict() for name, rec in self._costs.items()}
        total_cost = sum(r["total_cost_usd"] for r in records.values())
        total_calls = sum(r["total_calls"] for r in records.values())
        return {
            "models": records,
            "total_cost_usd": round(total_cost, 6),
            "total_calls": total_calls,
            "protocol_version": PROTOCOL_VERSION,
        }

    def reset_health(self, model_name: str) -> None:
        """Manually reset a model to healthy (e.g. after maintenance)."""
        self._health[model_name] = True
        self._failure_counts[model_name] = 0
        audit(event="llm_model_health_reset", model=model_name, protocol_version=PROTOCOL_VERSION)

    def list_models(self) -> List[Dict[str, Any]]:
        """List all configured models with status."""
        return [
            {
                "name": m.name,
                "provider": m.provider,
                "model": m.model,
                "priority": m.priority.value,
                "is_active": m.is_active,
                "is_healthy": self._health.get(m.name, True),
                "task_types": m.task_types,
                "protocol_version": PROTOCOL_VERSION,
            }
            for m in self.models
        ]
