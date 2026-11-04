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

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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
    "local_qwen": ModelDescriptor(
        id="local_qwen",
        provider="local_transformers",
        display_name="Local Qwen (downloaded model)",
        tier=ModelTier.LOCAL,
        cost_tier=CostTier.FREE,
        context_window=32_768,
        max_output=2_048,
        strengths=("local_privacy", "offline", "agent_executor"),
        capabilities={"tool_calling": False, "computer_use": False, "vision": False, "reasoning": True, "streaming": False},
        is_local=True,
    ),
    "claude-opus-5-5": ModelDescriptor(
        id="claude-opus-5-5",
        provider="anthropic",
        display_name="Claude Opus 5.5",
        tier=ModelTier.FRONTIER,
        cost_tier=CostTier.HIGH,
        context_window=1_000_000,
        max_output=131_072,
        strengths=("complex_reasoning", "system_architecture", "security_audit", "deep_refactoring"),
        capabilities={"tool_calling": True, "computer_use": True, "vision": True, "reasoning": True, "streaming": True},
    ),
    "claude-sonnet-5-5": ModelDescriptor(
        id="claude-sonnet-5-5",
        provider="anthropic",
        display_name="Claude Sonnet 5.5",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        max_output=131_072,
        strengths=("coding", "agentic_workflows", "computer_use", "tool_use", "data_analysis"),
        capabilities={"tool_calling": True, "computer_use": True, "vision": True, "reasoning": True, "streaming": True},
    ),
    "claude-haiku-5-5": ModelDescriptor(
        id="claude-haiku-5-5",
        provider="anthropic",
        display_name="Claude Haiku 5.5",
        tier=ModelTier.FAST,
        cost_tier=CostTier.LOW,
        context_window=1_000_000,
        max_output=131_072,
        strengths=("low_latency", "fast_triage", "classification", "summarization"),
        capabilities={"tool_calling": True, "computer_use": False, "vision": True, "reasoning": False, "streaming": True},
    ),
    "claude-fable-5-1": ModelDescriptor(
        id="claude-fable-5-1",
        provider="anthropic",
        display_name="Claude Fable 5.1",
        tier=ModelTier.STANDARD,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        max_output=131_072,
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
        provider_registry: Any = None,
        request_timeout: float = 60.0,
    ):
        self.catalog = catalog or dict(DEFAULT_MODEL_CATALOG)
        self.default_model = default_model if default_model in self.catalog else "claude-sonnet-5-5"
        self.provider_registry = provider_registry
        self.request_timeout = request_timeout
        self._availability: dict[str, bool] = {}
        self._profiles: dict[str, Any] = {}
        self._ollama_models: set[str] = set()
        self._local_model_providers: dict[str, Any] = {}
        self._circuit_breakers: dict[str, Any] = {}
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

    def get_circuit_breaker(self, provider: str) -> Any:
        p = provider.lower()
        if hasattr(self, "provider_registry") and self.provider_registry is not None and hasattr(self.provider_registry, "get_circuit_breaker"):
            return self.provider_registry.get_circuit_breaker(p)
        if p not in self._circuit_breakers:
            from synapse.llm.providers.circuit_breaker import CircuitBreaker
            self._circuit_breakers[p] = CircuitBreaker(name=p, failure_threshold=5, recovery_timeout_sec=30.0)
        return self._circuit_breakers[p]

    def is_provider_available(self, provider: str) -> bool:
        """Return observed readiness, never assuming a local server is running."""
        p = provider.lower()
        cb = self.get_circuit_breaker(p)
        if not cb.allow_request():
            return False
        if p == "ollama":
            return self._availability.get(p, False)
        return self._availability.get(p, bool(os.getenv(f"{p.upper()}_API_KEY")))

    async def _registry(self) -> Any:
        if self.provider_registry is None:
            from synapse.api.routes.providers import provider_service
            self.provider_registry = provider_service.registry
        return self.provider_registry

    async def _probe_ollama(self, timeout: float = 2.0) -> list[str]:
        import httpx
        root = os.getenv("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/").removesuffix("/v1")
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{root}/api/tags")
                response.raise_for_status()
            models = [m.get("name", "") for m in response.json().get("models", [])]
            self._ollama_models = {m for m in models if m}
            self._availability["ollama"] = True
            return sorted(self._ollama_models)
        except Exception as exc:
            self._ollama_models = set()
            self._availability["ollama"] = False
            logger.info("Ollama is unavailable: %s", exc)
            return []

    async def refresh_providers(self) -> None:
        """Refresh local and registry-backed readiness and discovered models."""
        await self._probe_ollama()
        registry = await self._registry()
        for profile in await registry.list():
            self._profiles[profile.id] = profile
            probe = await registry.test_connection(profile.id, timeout=3.0)
            self._availability[profile.id] = probe.success
            if not probe.success:
                continue
            models = await registry.discover_models(profile.id, timeout=3.0)
            names = [m.id for m in models] or list(profile.metadata.get("legacy_models", []))
            if profile.default_model and profile.default_model not in names:
                names.insert(0, profile.default_model)
            for name in names:
                if name in self.catalog and self.catalog[name].provider != profile.id:
                    continue
                self.catalog[name] = ModelDescriptor(
                    id=name, provider=profile.id, display_name=name,
                    tier=ModelTier.LOCAL if profile.api_mode.value == "ollama" else ModelTier.STANDARD,
                    cost_tier=CostTier.FREE if profile.api_mode.value == "ollama" else CostTier.MEDIUM,
                    context_window=next((m.context_window or 128_000 for m in models if m.id == name), 128_000),
                    max_output=next((m.max_output or 8_192 for m in models if m.id == name), 8_192),
                    strengths=("configured_provider",), capabilities={"streaming": True},
                    is_local=profile.api_mode.value == "ollama",
                )
        try:
            from synapse.models import get_model_registry
            for manifest in get_model_registry().list():
                if manifest.status != "downloaded" or not manifest.local_path or not Path(manifest.local_path).is_dir():
                    continue
                self.catalog[manifest.model_id] = ModelDescriptor(
                    id=manifest.model_id,
                    provider="local_transformers",
                    display_name=f"Local {manifest.model_id}",
                    tier=ModelTier.LOCAL,
                    cost_tier=CostTier.FREE,
                    context_window=32_768,
                    max_output=2_048,
                    strengths=("local_privacy", "offline", "agent_executor"),
                    capabilities={"reasoning": True, "streaming": False},
                    is_local=True,
                )
        except Exception as exc:
            logger.debug("local model registry refresh failed: %s", exc)

    async def route_async(self, task_description: str,
                          requirements: Optional[dict[str, Any]] = None) -> RouteDecision:
        await self.refresh_providers()
        requirements = requirements or {}
        explicit_model = requirements.get("model")
        local_only = bool(requirements.get("local_only") or requirements.get("privacy"))
        if explicit_model:
            manifest = None
            try:
                from synapse.models import get_model_registry
                manifest = get_model_registry().get(explicit_model)
            except Exception:
                manifest = None
            if manifest is not None and manifest.status == "downloaded" and manifest.local_path:
                self.catalog.setdefault(
                    explicit_model,
                    ModelDescriptor(
                        id=explicit_model,
                        provider="local_transformers",
                        display_name=f"Local {explicit_model}",
                        tier=ModelTier.LOCAL,
                        cost_tier=CostTier.FREE,
                        context_window=32_768,
                        max_output=2_048,
                        strengths=("local_privacy", "offline", "agent_executor"),
                        capabilities={"reasoning": True, "streaming": False},
                        is_local=True,
                    ),
                )
        if local_only and explicit_model and explicit_model in self.catalog:
            decision = self.route(task_description, {**requirements, "model": explicit_model})
            decision.fallback_chain = []
            decision.provider_available = self._candidate_ready(
                decision.provider, decision.model, requirements, check_availability=True
            )
            return decision
        decision = self.route(task_description, requirements)
        if local_only:
            # Preserve the established Ollama default for generic local-only routing.
            # A downloaded Transformers model participates only when explicitly selected
            # by model id, preventing a new local artifact from silently changing policy.
            return decision
        return decision

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
                provider_available=self.is_provider_available("ollama"),
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
        decision = await self.route_async(task_description, requirements)
        effective_prompt = prompt or task_description
        self._stats["execution_calls"] += 1
        attempts: list[dict[str, Any]] = []
        requirements = requirements or {}

        candidates = [{"provider": decision.provider, "model": decision.model}]
        candidates.extend(decision.fallback_chain)
        # Prioritize ready/available candidates; fall back to all eligible candidates
        ready_candidates = [
            c for c in candidates
            if self._candidate_ready(c["provider"], c["model"], requirements, check_availability=True)
        ]
        if ready_candidates:
            candidates = ready_candidates
        else:
            candidates = [
                c for c in candidates
                if self._candidate_ready(c["provider"], c["model"], requirements, check_availability=False)
            ]
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            cand_provider, cand_model = candidate["provider"], candidate["model"]
            if (cand_provider, cand_model) in seen:
                continue
            seen.add((cand_provider, cand_model))

            cb = self.get_circuit_breaker(cand_provider)
            if not cb.allow_request():
                logger.info("Skipping candidate (%s/%s): circuit breaker is OPEN", cand_provider, cand_model)
                attempts.append({
                    "provider": cand_provider,
                    "model": cand_model,
                    "error": f"Circuit breaker OPEN (retry in {cb.time_until_retry():.1f}s)",
                    "duration": 0.0,
                })
                continue

            candidate_start = time.monotonic()
            try:
                if cand_provider == "local_transformers":
                    provider_instance = self._local_model_providers.get(cand_model)
                    if provider_instance is None:
                        from synapse.models import get_model_registry
                        from synapse.llm.local_model import LocalTransformersProvider
                        manifest = get_model_registry().get(cand_model)
                        if manifest is None or manifest.status != "downloaded" or not manifest.local_path:
                            raise RuntimeError("local model manifest is not downloaded")
                        provider_instance = LocalTransformersProvider(manifest.local_path)
                        self._local_model_providers[cand_model] = provider_instance
                    response = await asyncio.wait_for(
                        provider_instance.generate(effective_prompt, **kwargs),
                        timeout=self.request_timeout,
                    )
                else:
                    from synapse.llm.provider import LiteLLMProvider

                    model, api_base, api_key = await self._execution_config(
                        cand_provider, cand_model,
                    )
                    provider_instance = LiteLLMProvider(
                        name=cand_provider, model=model, api_base=api_base, api_key=api_key,
                    )
                    response = await asyncio.wait_for(
                        provider_instance.generate(effective_prompt, **kwargs),
                        timeout=self.request_timeout,
                    )
                cb.record_success()
                duration = round(time.monotonic() - candidate_start, 3)
                return {
                    "success": True, "content": response.get("content", ""),
                    "model_used": cand_model, "provider_used": cand_provider,
                    "route_decision": decision.to_dict(),
                    "usage": response.get("usage", {}),
                    "duration_seconds": duration,
                    "total_duration_seconds": round(time.monotonic() - start_time, 3),
                    "attempts": attempts, "protocol_version": PROTOCOL_VERSION,
                }
            except Exception as exc:
                cb.record_failure(exc)
                duration = round(time.monotonic() - candidate_start, 3)
                error = (f"Request exceeded {self.request_timeout:g}s"
                         if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else str(exc))
                logger.warning("OmniRouter candidate failed (%s/%s): %s",
                               cand_provider, cand_model, error)
                attempts.append({"provider": cand_provider, "model": cand_model,
                                 "error": error[:500], "duration": duration})

        self._stats["execution_failures"] += 1
        reason = ("No provider satisfies the requested constraints or is available."
                  if not candidates else "All available model candidates failed.")
        return {
            "success": False, "error": reason,
            "content": "",
            "model_used": None, "provider_used": None,
            "route_decision": decision.to_dict(), "usage": {},
            "total_duration_seconds": round(time.monotonic() - start_time, 3),
            "attempts": attempts, "protocol_version": PROTOCOL_VERSION,
        }

    def _candidate_ready(
        self,
        provider: str,
        model: str,
        requirements: dict[str, Any],
        check_availability: bool = True,
    ) -> bool:
        descriptor = self.catalog.get(model)
        if descriptor is None or descriptor.provider != provider:
            return False
        if check_availability and provider == "local_transformers":
            try:
                from synapse.models import get_model_registry
                manifest = get_model_registry().get(model)
                return bool(
                    manifest
                    and manifest.status == "downloaded"
                    and manifest.local_path
                    and Path(manifest.local_path).is_dir()
                )
            except Exception:
                return False
        if check_availability and provider == "ollama" and self._ollama_models and not any(
            model == name or model == name.split(":", 1)[0] for name in self._ollama_models
        ):
            return False
        return True

    async def _execution_config(self, provider: str, model: str) -> tuple[str, str | None, str | None]:
        profile = self._profiles.get(provider)
        if provider == "local_transformers":
            return model, None, None
        if provider == "ollama":
            return (model if model.startswith("ollama/") else f"ollama/{model}",
                    os.getenv("OLLAMA_API_BASE", "http://localhost:11434"), None)
        if profile is None:
            return model, None, None
        api_key = None
        if profile.credential_ref:
            registry = await self._registry()
            api_key = (await registry.resolve_credential(profile)).reveal()
        from synapse.llm.providers.profile import ApiMode
        prefixes = {
            ApiMode.OPENAI_CHAT: "openai/", ApiMode.OPENAI_RESPONSES: "openai/",
            ApiMode.OPENAI_COMPATIBLE: "openai/", ApiMode.ANTHROPIC_MESSAGES: "anthropic/",
            ApiMode.GEMINI_NATIVE: "gemini/", ApiMode.OLLAMA: "ollama/",
            ApiMode.AZURE_OPENAI: "azure/", ApiMode.BEDROCK: "bedrock/",
            ApiMode.VERTEX_AI: "vertex_ai/",
        }
        if profile.api_mode == ApiMode.CUSTOM_HTTP:
            raise RuntimeError(f"Provider '{provider}' uses an unsupported generation protocol")
        prefix = prefixes[profile.api_mode]
        return (model if "/" in model else prefix + model), profile.base_url, api_key

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
        """Return observed readiness without making network requests."""
        providers = {
            name: {
                "available": self.is_provider_available(name),
                "key_configured": bool(os.getenv(f"{name.upper()}_API_KEY")),
                "tier": "local" if name == "ollama" else "frontier",
            }
            for name in ("anthropic", "openai", "ollama")
        }
        for name, profile in self._profiles.items():
            providers[name] = {
                "available": self.is_provider_available(name),
                "credential_configured": bool(profile.credential_ref),
                "enabled": profile.enabled,
                "tier": "local" if profile.api_mode.value == "ollama" else "configured",
            }
        providers["ollama"]["installed_models"] = sorted(self._ollama_models)
        providers["ollama"]["endpoint"] = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        return {"providers": providers, "default_model": self.default_model,
                "protocol_version": PROTOCOL_VERSION}

    async def health_check_async(self) -> dict[str, Any]:
        """Refresh provider health before reporting it to API clients."""
        await self.refresh_providers()
        return self.health_check()


# Global default instance
_default_omnirouter: Optional[OmniRouter] = None


def get_omnirouter() -> OmniRouter:
    """Get or create singleton OmniRouter instance."""
    global _default_omnirouter
    if _default_omnirouter is None:
        _default_omnirouter = OmniRouter()
    return _default_omnirouter
