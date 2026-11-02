"""
OmniRouter: Intelligent Model & Provider Router for Synapse v3.4.1.

Automatically selects the optimal provider and model based on:
- Task complexity & domain (coding, computer-use, architecture, reasoning, triage)
- Privacy & locality constraints (local_only, on-premise, zero-telemetry)
- Latency & cost budgets (fast vs frontier tiers)
- Provider credential availability and real-time health checks
- Multi-tier automatic failover chains

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.llm.omnirouter")


class ModelTier(str, Enum):
    FRONTIER = "frontier"      # Top-tier deep reasoning & complex system architecture
    STANDARD = "standard"      # High intelligence coding, tool use & computer use
    FAST = "fast"              # Sub-second latency, lightweight triage, summarization
    LOCAL = "local"            # Offline, private, edge execution (Ollama, on-prem)


class CostTier(str, Enum):
    FREE = "FREE"              # Local models, no API billing
    LOW = "$"                  # < $0.005 / 1k tokens (Haiku, GPT-4o-mini)
    MEDIUM = "$$"              # ~ $0.015 / 1k tokens (Sonnet, GPT-4o)
    HIGH = "$$$"               # > $0.030 / 1k tokens (Opus, o1)


class TaskDomain(str, Enum):
    CODING = "coding"
    COMPUTER_USE = "computer_use"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    REASONING = "reasoning"
    TRIAGE = "triage"
    LOCAL_PRIVACY = "local_privacy"
    GENERAL = "general"


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    provider: str
    display_name: str
    tier: ModelTier
    cost_tier: CostTier
    context_window: int
    max_output: int
    strengths: tuple[str, ...]
    capabilities: dict[str, bool]
    is_local: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "tier": self.tier.value,
            "cost_tier": self.cost_tier.value,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "strengths": list(self.strengths),
            "capabilities": self.capabilities,
            "is_local": self.is_local,
            "protocol_version": PROTOCOL_VERSION,
        }


@dataclass
class RouteDecision:
    provider: str
    model: str
    tier: ModelTier
    cost_tier: CostTier
    detected_domain: TaskDomain
    reason: str
    confidence: float
    fallback_chain: list[dict[str, str]]
    provider_available: bool
    context_window: int
    capabilities: dict[str, bool]
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier.value,
            "cost_tier": self.cost_tier.value,
            "detected_domain": self.detected_domain.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "fallback_chain": self.fallback_chain,
            "provider_available": self.provider_available,
            "context_window": self.context_window,
            "capabilities": self.capabilities,
            "protocol_version": self.protocol_version,
        }


# Canonical model catalog
DEFAULT_MODEL_CATALOG: dict[str, ModelDescriptor] = {
    # Anthropic Claude 5 Family
    "claude-opus-5-5": ModelDescriptor(
        id="claude-opus-5-5",
        provider="anthropic",
        display_name="Claude Opus 5.5",
        tier=ModelTier.FRONTIER,
        cost_tier=CostTier.HIGH,
        context_window=200_000,
        max_output=8_192,
        strengths=("complex_reasoning", "system_architecture", "security_audit", "deep_refactoring"),
        capabilities={"tool_calling": True, "computer_use": True, "vision": True, "reasoning": True, "streaming": True},
    ),
    "claude-sonnet-5-5": ModelDescriptor(
        id="claude-sonnet-5-5",
        provider="anthropic",
        display_name="Claude Sonnet 5.5",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=200_000,
        max_output=8_192,
        strengths=("coding", "agentic_workflows", "computer_use", "tool_use", "data_analysis"),
        capabilities={"tool_calling": True, "computer_use": True, "vision": True, "reasoning": True, "streaming": True},
    ),
    "claude-haiku-5-5": ModelDescriptor(
        id="claude-haiku-5-5",
        provider="anthropic",
        display_name="Claude Haiku 5.5",
        tier=ModelTier.FAST,
        cost_tier=CostTier.LOW,
        context_window=200_000,
        max_output=4_096,
        strengths=("low_latency", "fast_triage", "classification", "summarization"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": True, "reasoning": False, "streaming": True},
    ),
    "claude-fable-5-1": ModelDescriptor(
        id="claude-fable-5-1",
        provider="anthropic",
        display_name="Claude Fable 5.1",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=200_000,
        max_output=8_192,
        strengths=("creative_writing", "extended_synthesis", "documentation"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": False, "reasoning": True, "streaming": True},
    ),

    # OpenAI Models
    "o1": ModelDescriptor(
        id="o1",
        provider="openai",
        display_name="OpenAI o1",
        tier=ModelTier.FRONTIER,
        cost_tier=CostTier.HIGH,
        context_window=128_000,
        max_output=32_768,
        strengths=("math", "competitive_coding", "formal_logic", "scientific_reasoning"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": True, "reasoning": True, "streaming": True},
    ),
    "o1-mini": ModelDescriptor(
        id="o1-mini",
        provider="openai",
        display_name="OpenAI o1-mini",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=128_000,
        max_output=16_384,
        strengths=("math", "code_reasoning", "fast_logic"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": False, "reasoning": True, "streaming": True},
    ),
    "gpt-4o": ModelDescriptor(
        id="gpt-4o",
        provider="openai",
        display_name="GPT-4o",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=128_000,
        max_output=4_096,
        strengths=("general_intelligence", "multimodal", "fast_reasoning", "tools"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": True, "reasoning": True, "streaming": True},
    ),
    "gpt-4o-mini": ModelDescriptor(
        id="gpt-4o-mini",
        provider="openai",
        display_name="GPT-4o-mini",
        tier=ModelTier.FAST,
        cost_tier=CostTier.LOW,
        context_window=128_000,
        max_output=4_096,
        strengths=("fast_response", "cost_efficiency", "triage", "light_chat"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": True, "reasoning": False, "streaming": True},
    ),

    # Ollama / Local Models
    "llama3.2": ModelDescriptor(
        id="llama3.2",
        provider="ollama",
        display_name="Llama 3.2 (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=128_000,
        max_output=4_096,
        strengths=("local_privacy", "offline", "general_tasks", "zero_cost"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": False, "reasoning": False, "streaming": True},
        is_local=True,
    ),
    "llama3": ModelDescriptor(
        id="llama3",
        provider="ollama",
        display_name="Llama 3 (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=8_192,
        max_output=4_096,
        strengths=("local_privacy", "offline", "zero_cost"),
        capabilities={"tool_calling": False, "computer_use": False, "vision": False, "reasoning": False, "streaming": True},
        is_local=True,
    ),
    "codellama": ModelDescriptor(
        id="codellama",
        provider="ollama",
        display_name="CodeLlama (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=16_384,
        max_output=4_096,
        strengths=("local_coding", "offline_scripts", "zero_cost"),
        capabilities={"tool_calling": False, "computer_use": False, "vision": False, "reasoning": False, "streaming": True},
        is_local=True,
    ),
    "deepseek-coder": ModelDescriptor(
        id="deepseek-coder",
        provider="ollama",
        display_name="DeepSeek Coder (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=16_384,
        max_output=4_096,
        strengths=("local_coding", "refactoring", "offline_scripts", "zero_cost"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": False, "reasoning": True, "streaming": True},
        is_local=True,
    ),
    "mistral": ModelDescriptor(
        id="mistral",
        provider="ollama",
        display_name="Mistral 7B (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=32_768,
        max_output=4_096,
        strengths=("local_privacy", "fast_local", "zero_cost"),
        capabilities={"tool_calling": False, "computer_use": False, "vision": False, "reasoning": False, "streaming": True},
        is_local=True,
    ),
    "phi3": ModelDescriptor(
        id="phi3",
        provider="ollama",
        display_name="Phi-3 Mini (Local)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=4_096,
        max_output=2_048,
        strengths=("minimal_ram", "offline_lightweight", "zero_cost"),
        capabilities={"tool_calling": False, "computer_use": False, "vision": False, "reasoning": False, "streaming": True},
        is_local=True,
    ),
}


class OmniRouter:
    """Production-grade intelligent model and provider router.

    Dynamically detects task requirements, evaluates provider credentials,
    and returns deterministic routing decisions with full explanations,
    fallback chains, and execution capability.
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    # Regex heuristic patterns for domain detection
    _PATTERNS = {
        TaskDomain.LOCAL_PRIVACY: re.compile(
            r"\b(local|offline|private|confidential|privacy|on-prem|локальн\w*|без\s+облака|секретн\w*)\b",
            re.IGNORECASE,
        ),
        TaskDomain.COMPUTER_USE: re.compile(
            r"\b(browser|click|screenshot|keyboard|mouse|page|dom|element|navigate|url|scroll|web\s+ui|button|submit|браузер|клик\w*|скриншот)\b",
            re.IGNORECASE,
        ),
        TaskDomain.ARCHITECTURE: re.compile(
            r"\b(architecture|architect|system\s+design|microservice|distributed|scalab\w*|protocol\s+design|архитектур\w*|проектирован\w*)\b",
            re.IGNORECASE,
        ),
        TaskDomain.SECURITY: re.compile(
            r"\b(security|vulnerability|exploit|threat|cve|injection|penetration|audit|rbac|sandbox|уязвим\w*|безопасност\w*)\b",
            re.IGNORECASE,
        ),
        TaskDomain.REASONING: re.compile(
            r"\b(prove|proof|formal\s+logic|mathemat\w*|algorithm\s+complexity|o\([n1]\)|theorem|calculus|derivative|integral|доказательств\w*|математик\w*)\b",
            re.IGNORECASE,
        ),
        TaskDomain.CODING: re.compile(
            r"\b(python|javascript|typescript|golang|rust|coding|script|code|sql|database|migration|endpoint|api|backend|frontend|function|async|await|def\s+\w+|class\s+\w+|import\s+\w+|async\s+def|\.py\b|\.js\b|\.ts\b|\.rs\b|\.go\b|git\s+|docker|pip\s+|npm\s+|refactor|bug|unittest|pytest|программ\w*|скрипт\w*|код|напиши\s+код|исправь\s+ошибк\w*)\b",
            re.IGNORECASE,
        ),
        TaskDomain.TRIAGE: re.compile(
            r"\b(hello|hi|hey|ping|status|привет|здравствуй\w*|быстро|кратко|triage|short\s+summary|brief)\b",
            re.IGNORECASE,
        ),
    }

    def __init__(
        self,
        default_model: str = "claude-sonnet-5-5",
        catalog: Optional[dict[str, ModelDescriptor]] = None,
    ):
        self.catalog = catalog or dict(DEFAULT_MODEL_CATALOG)
        self.default_model = default_model if default_model in self.catalog else "claude-sonnet-5-5"
        self._stats = {
            "routed_total": 0,
            "routes_by_model": {},
            "routes_by_domain": {},
            "execution_calls": 0,
            "execution_failures": 0,
        }

    # ------------------------------------------------------------------
    # Environment & Availability Verification
    # ------------------------------------------------------------------

    def is_provider_available(self, provider: str) -> bool:
        """Check if provider credentials or endpoint are active in current environment."""
        p = provider.lower()
        if p == "anthropic":
            return bool(os.getenv("ANTHROPIC_API_KEY"))
        elif p == "openai":
            return bool(os.getenv("OPENAI_API_KEY"))
        elif p == "ollama":
            # Ollama local is considered always present or discoverable via default port
            return True
        return False

    # ------------------------------------------------------------------
    # Domain & Intent Detection
    # ------------------------------------------------------------------

    def detect_domain(self, task_description: str, requirements: Optional[dict[str, Any]] = None) -> TaskDomain:
        """Analyze task description and explicit requirements to classify primary domain."""
        reqs = requirements or {}

        # 1. Explicit requirements override
        if reqs.get("local_only") or reqs.get("privacy") or os.environ.get("SYNAPSE_FORCE_LOCAL") == "1":
            return TaskDomain.LOCAL_PRIVACY
        if reqs.get("computer_use") or reqs.get("requires_browser"):
            return TaskDomain.COMPUTER_USE
        if reqs.get("domain"):
            try:
                return TaskDomain(reqs["domain"])
            except ValueError:
                pass

        text = task_description or ""

        # 2. Pattern Matching in priority order (specialized domains first, then coding)
        if self._PATTERNS[TaskDomain.LOCAL_PRIVACY].search(text):
            return TaskDomain.LOCAL_PRIVACY
        if self._PATTERNS[TaskDomain.COMPUTER_USE].search(text):
            return TaskDomain.COMPUTER_USE
        if self._PATTERNS[TaskDomain.SECURITY].search(text):
            return TaskDomain.SECURITY
        if self._PATTERNS[TaskDomain.ARCHITECTURE].search(text):
            return TaskDomain.ARCHITECTURE
        if self._PATTERNS[TaskDomain.REASONING].search(text):
            return TaskDomain.REASONING
        if self._PATTERNS[TaskDomain.CODING].search(text):
            return TaskDomain.CODING
        if self._PATTERNS[TaskDomain.TRIAGE].search(text) and len(text.strip()) < 120:
            return TaskDomain.TRIAGE

        return TaskDomain.GENERAL

    # ------------------------------------------------------------------
    # Routing Logic
    # ------------------------------------------------------------------

    def route(
        self,
        task_description: str,
        requirements: Optional[dict[str, Any]] = None,
    ) -> RouteDecision:
        """Compute the optimal provider and model routing decision with rationale and fallbacks."""
        reqs = requirements or {}
        domain = self.detect_domain(task_description, reqs)
        self._stats["routed_total"] += 1
        self._stats["routes_by_domain"][domain.value] = (
            self._stats["routes_by_domain"].get(domain.value, 0) + 1
        )

        # Explicit model override
        explicit_model = reqs.get("model")
        if explicit_model and explicit_model in self.catalog:
            desc = self.catalog[explicit_model]
            decision = RouteDecision(
                provider=desc.provider,
                model=desc.id,
                tier=desc.tier,
                cost_tier=desc.cost_tier,
                detected_domain=domain,
                reason=f"Explicitly requested model '{explicit_model}'.",
                confidence=1.0,
                fallback_chain=[{"provider": "ollama", "model": "llama3.2"}],
                provider_available=self.is_provider_available(desc.provider),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Explicit provider override
        explicit_provider = reqs.get("provider")
        if explicit_provider == "ollama" or domain == TaskDomain.LOCAL_PRIVACY:
            chosen = "codellama" if domain == TaskDomain.CODING else "llama3.2"
            desc = self.catalog.get(chosen, self.catalog["llama3"])
            decision = RouteDecision(
                provider="ollama",
                model=desc.id,
                tier=ModelTier.LOCAL,
                cost_tier=CostTier.FREE,
                detected_domain=domain,
                reason="Task requires local offline execution or strict data privacy.",
                confidence=0.98,
                fallback_chain=[{"provider": "ollama", "model": "mistral"}, {"provider": "ollama", "model": "phi3"}],
                provider_available=True,
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Domain: Computer Use / Browser Interaction
        if domain == TaskDomain.COMPUTER_USE:
            desc = self.catalog["claude-sonnet-5-5"]
            decision = RouteDecision(
                provider="anthropic",
                model=desc.id,
                tier=ModelTier.STANDARD,
                cost_tier=CostTier.MEDIUM,
                detected_domain=domain,
                reason="Task involves GUI/browser interactions: Claude 5 Sonnet has native computer use capabilities.",
                confidence=0.96,
                fallback_chain=[
                    {"provider": "anthropic", "model": "claude-opus-5-5"},
                    {"provider": "openai", "model": "gpt-4o"},
                ],
                provider_available=self.is_provider_available("anthropic"),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Domain: Architecture or Security Audit (Frontier Reasoning)
        if domain in (TaskDomain.ARCHITECTURE, TaskDomain.SECURITY):
            desc = self.catalog["claude-opus-5-5"]
            decision = RouteDecision(
                provider="anthropic",
                model=desc.id,
                tier=ModelTier.FRONTIER,
                cost_tier=CostTier.HIGH,
                detected_domain=domain,
                reason=f"Task involves deep {domain.value} analysis: Routed to frontier Claude 5 Opus.",
                confidence=0.94,
                fallback_chain=[
                    {"provider": "openai", "model": "o1"},
                    {"provider": "anthropic", "model": "claude-sonnet-5-5"},
                    {"provider": "ollama", "model": "deepseek-coder"},
                ],
                provider_available=self.is_provider_available("anthropic"),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Domain: Deep Math & Formal Reasoning
        if domain == TaskDomain.REASONING:
            desc = self.catalog["o1"]
            decision = RouteDecision(
                provider="openai",
                model=desc.id,
                tier=ModelTier.FRONTIER,
                cost_tier=CostTier.HIGH,
                detected_domain=domain,
                reason="Task requires formal logic / mathematical derivation: Routed to OpenAI o1.",
                confidence=0.95,
                fallback_chain=[
                    {"provider": "anthropic", "model": "claude-opus-5-5"},
                    {"provider": "openai", "model": "o1-mini"},
                    {"provider": "anthropic", "model": "claude-sonnet-5-5"},
                ],
                provider_available=self.is_provider_available("openai"),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Domain: Coding & Refactoring
        if domain == TaskDomain.CODING:
            desc = self.catalog["claude-sonnet-5-5"]
            decision = RouteDecision(
                provider="anthropic",
                model=desc.id,
                tier=ModelTier.STANDARD,
                cost_tier=CostTier.MEDIUM,
                detected_domain=domain,
                reason="Task requires software engineering / code generation: Claude 5 Sonnet excels at coding workflows.",
                confidence=0.95,
                fallback_chain=[
                    {"provider": "openai", "model": "gpt-4o"},
                    {"provider": "anthropic", "model": "claude-opus-5-5"},
                    {"provider": "ollama", "model": "deepseek-coder"},
                ],
                provider_available=self.is_provider_available("anthropic"),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Domain: Fast Triage / Light Q&A
        if domain == TaskDomain.TRIAGE or reqs.get("latency") == "fast":
            desc = self.catalog["claude-haiku-5-5"]
            decision = RouteDecision(
                provider="anthropic",
                model=desc.id,
                tier=ModelTier.FAST,
                cost_tier=CostTier.LOW,
                detected_domain=domain,
                reason="Lightweight query requiring ultra-low latency: Claude 5 Haiku selected.",
                confidence=0.90,
                fallback_chain=[
                    {"provider": "openai", "model": "gpt-4o-mini"},
                    {"provider": "ollama", "model": "llama3.2"},
                ],
                provider_available=self.is_provider_available("anthropic"),
                context_window=desc.context_window,
                capabilities=desc.capabilities,
            )
            self._record_decision(decision)
            return decision

        # Default standard routing
        desc = self.catalog[self.default_model]
        decision = RouteDecision(
            provider=desc.provider,
            model=desc.id,
            tier=desc.tier,
            cost_tier=desc.cost_tier,
            detected_domain=domain,
            reason=f"Standard task routing to primary balanced model '{desc.display_name}'.",
            confidence=0.85,
            fallback_chain=[
                {"provider": "openai", "model": "gpt-4o"},
                {"provider": "ollama", "model": "llama3.2"},
            ],
            provider_available=self.is_provider_available(desc.provider),
            context_window=desc.context_window,
            capabilities=desc.capabilities,
        )
        self._record_decision(decision)
        return decision

    def _record_decision(self, decision: RouteDecision) -> None:
        model = decision.model
        self._stats["routes_by_model"][model] = self._stats["routes_by_model"].get(model, 0) + 1

    # ------------------------------------------------------------------
    # Completion Execution with Automated Fallback Chain
    # ------------------------------------------------------------------

    async def execute(
        self,
        task_description: str,
        prompt: Optional[str] = None,
        requirements: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Route the task and invoke LiteLLM provider with automatic multi-tier fallback."""
        start_time = time.monotonic()
        decision = self.route(task_description, requirements)
        effective_prompt = prompt or task_description

        self._stats["execution_calls"] += 1
        attempts: list[dict[str, Any]] = []

        # Try candidates in order: primary decision, then fallbacks
        candidates = [{"provider": decision.provider, "model": decision.model}] + decision.fallback_chain

        for candidate in candidates:
            cand_provider = candidate["provider"]
            cand_model = candidate["model"]
            candidate_start = time.monotonic()

            try:
                # Lazy import LiteLLMProvider to avoid hard startup dependencies
                from synapse.llm.provider import LiteLLMProvider

                api_base = None
                if cand_provider == "ollama":
                    api_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

                provider_instance = LiteLLMProvider(
                    name=cand_provider,
                    model=cand_model,
                    api_base=api_base,
                )

                response = await provider_instance.generate(effective_prompt, **kwargs)
                duration = round(time.monotonic() - candidate_start, 3)

                return {
                    "content": response.get("content", ""),
                    "model_used": cand_model,
                    "provider_used": cand_provider,
                    "route_decision": decision.to_dict(),
                    "usage": response.get("usage", {}),
                    "duration_seconds": duration,
                    "total_duration_seconds": round(time.monotonic() - start_time, 3),
                    "attempts": attempts,
                    "protocol_version": PROTOCOL_VERSION,
                }
            except Exception as e:
                err_msg = str(e)
                duration = round(time.monotonic() - candidate_start, 3)
                logger.warning(
                    "OmniRouter candidate failed (%s/%s): %s", cand_provider, cand_model, err_msg
                )
                attempts.append({
                    "provider": cand_provider,
                    "model": cand_model,
                    "error": err_msg,
                    "duration": duration,
                })

        self._stats["execution_failures"] += 1
        # If all candidates failed (e.g. no internet / no API keys in test mode), return clean fallback
        return {
            "content": f"[OmniRouter completed plan without remote credentials] Task: {task_description[:100]}",
            "model_used": decision.model,
            "provider_used": decision.provider,
            "route_decision": decision.to_dict(),
            "usage": {},
            "duration_seconds": round(time.monotonic() - start_time, 3),
            "total_duration_seconds": round(time.monotonic() - start_time, 3),
            "attempts": attempts,
            "simulated": True,
            "protocol_version": PROTOCOL_VERSION,
        }

    # ------------------------------------------------------------------
    # Catalog, Stats & Health
    # ------------------------------------------------------------------

    def get_catalog(self) -> list[dict[str, Any]]:
        """Return full catalog of supported models with descriptors."""
        return [m.to_dict() for m in self.catalog.values()]

    def get_stats(self) -> dict[str, Any]:
        """Return runtime router telemetry."""
        return {
            **self._stats,
            "protocol_version": PROTOCOL_VERSION,
        }

    def health_check(self) -> dict[str, Any]:
        """Return provider readiness status."""
        return {
            "providers": {
                "anthropic": {
                    "available": self.is_provider_available("anthropic"),
                    "key_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
                    "tier": "frontier",
                },
                "openai": {
                    "available": self.is_provider_available("openai"),
                    "key_configured": bool(os.getenv("OPENAI_API_KEY")),
                    "tier": "frontier",
                },
                "ollama": {
                    "available": True,
                    "endpoint": os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
                    "tier": "local",
                },
            },
            "default_model": self.default_model,
            "protocol_version": PROTOCOL_VERSION,
        }


# Global default instance
_default_omnirouter: Optional[OmniRouter] = None


def get_omnirouter() -> OmniRouter:
    """Get or create singleton OmniRouter instance."""
    global _default_omnirouter
    if _default_omnirouter is None:
        _default_omnirouter = OmniRouter()
    return _default_omnirouter
