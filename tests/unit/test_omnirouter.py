"""
Unit tests for OmniRouter (Phase 3 & Phase 4).

Tests requirements for intelligent multi-provider, multi-model routing.
"""

import pytest
import os
from synapse.llm.omnirouter import (
    OmniRouter,
    ModelTier,
    CostTier,
    TaskDomain,
    get_omnirouter,
    PROTOCOL_VERSION,
)


@pytest.fixture
def router():
    return OmniRouter()


def test_protocol_version(router):
    assert router.PROTOCOL_VERSION == PROTOCOL_VERSION


def test_catalog_structure(router):
    catalog = router.get_catalog()
    assert len(catalog) >= 10
    ids = [m["id"] for m in catalog]
    assert "claude-sonnet-5-5" in ids
    assert "claude-opus-5-5" in ids
    assert "claude-haiku-5-5" in ids
    assert "gpt-4o" in ids
    assert "o1" in ids
    assert "llama3.2" in ids


def test_domain_detection_coding(router):
    domain = router.detect_domain("def calculate_fibonacci(n):\n    return n if n <= 1 else calculate_fibonacci(n-1) + calculate_fibonacci(n-2)")
    assert domain == TaskDomain.CODING


def test_domain_detection_computer_use(router):
    domain = router.detect_domain("Open the browser and click on the submit button on page https://example.com")
    assert domain == TaskDomain.COMPUTER_USE


def test_domain_detection_architecture(router):
    domain = router.detect_domain("Design a distributed system architecture for microservices event sourcing")
    assert domain == TaskDomain.ARCHITECTURE


def test_domain_detection_security(router):
    domain = router.detect_domain("Audit codebase for potential SQL injection vulnerabilities and threat vectors")
    assert domain == TaskDomain.SECURITY


def test_domain_detection_reasoning(router):
    domain = router.detect_domain("Prove mathematically that the algorithm complexity is O(n log n)")
    assert domain == TaskDomain.REASONING


def test_domain_detection_privacy(router):
    domain = router.detect_domain("Run this confidential query offline and local only")
    assert domain == TaskDomain.LOCAL_PRIVACY


def test_domain_detection_triage(router):
    domain = router.detect_domain("ping status")
    assert domain == TaskDomain.TRIAGE


def test_route_coding_selects_sonnet(router):
    decision = router.route("Write a python script to refactor the database migration logic")
    assert decision.model == "claude-sonnet-5-5"
    assert decision.provider == "anthropic"
    assert decision.tier == ModelTier.STANDARD
    assert "coding" in decision.reason.lower()
    assert len(decision.fallback_chain) > 0


def test_route_computer_use_selects_sonnet(router):
    decision = router.route("Navigate to web ui, take a screenshot and click the login button")
    assert decision.model == "claude-sonnet-5-5"
    assert decision.provider == "anthropic"
    assert decision.capabilities.get("computer_use") is True


def test_route_architecture_selects_opus(router):
    decision = router.route("Create enterprise architecture design and protocol specification")
    assert decision.model == "claude-opus-5-5"
    assert decision.provider == "anthropic"
    assert decision.tier == ModelTier.FRONTIER


def test_route_reasoning_selects_o1(router):
    decision = router.route("Prove the theorem step by step and calculate the formal complexity")
    assert decision.model == "o1"
    assert decision.provider == "openai"
    assert decision.tier == ModelTier.FRONTIER


def test_route_privacy_selects_ollama(router):
    decision = router.route("Process private data offline with local only execution")
    assert decision.provider == "ollama"
    assert decision.tier == ModelTier.LOCAL
    assert decision.cost_tier == CostTier.FREE


def test_route_explicit_model_override(router):
    decision = router.route("Any task description", requirements={"model": "gpt-4o"})
    assert decision.model == "gpt-4o"
    assert decision.provider == "openai"
    assert decision.confidence == 1.0


def test_route_explicit_local_requirement(router):
    decision = router.route("Perform data parsing", requirements={"local_only": True})
    assert decision.provider == "ollama"
    assert decision.tier == ModelTier.LOCAL


def test_health_check(router):
    health = router.health_check()
    assert "providers" in health
    assert "anthropic" in health["providers"]
    assert "openai" in health["providers"]
    assert "ollama" in health["providers"]
    assert health["protocol_version"] == PROTOCOL_VERSION


def test_stats_tracking(router):
    router.route("Write code for binary search")
    router.route("Hello world")
    stats = router.get_stats()
    assert stats["routed_total"] >= 2
    assert "claude-sonnet-5-5" in stats["routes_by_model"]


@pytest.mark.asyncio
async def test_execute_graceful_fallback(router):
    # Execute a task without remote API credentials; verify it executes or falls back gracefully
    result = await router.execute("Test task execution without live credentials")
    assert "content" in result
    assert "model_used" in result
    assert "route_decision" in result
    assert result["protocol_version"] == PROTOCOL_VERSION
