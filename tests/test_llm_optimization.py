"""Tests for LLM-driven prompt/code optimization.

Phase 10 - Production Autonomy & Self-Optimization.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.agents.optimizer import (
    OptimizerAgent,
    OptimizationRequest,
    OptimizationResponse
)


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for optimization."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value="""
# Optimized skill code
class OptimizedSkill:
    def execute(self, context):
        # Improved implementation
        return {"success": True, "optimized": True}
""")
    return provider


@pytest.fixture
def optimizer_agent(mock_llm_provider):
    """Create optimizer agent with mock LLM."""
    return OptimizerAgent(llm_provider=mock_llm_provider)


@pytest.mark.asyncio
async def test_optimizer_generates_improved_code(optimizer_agent):
    """Optimizer generates improved code."""
    request = OptimizationRequest(
        skill_name="test_skill",
        current_code="def execute(): pass",
        performance_metrics={"success_rate": 0.65, "latency_ms": 350},
        optimization_goal="improve_success_rate",
        seed=42
    )
    
    response = await optimizer_agent.optimize_code(request)
    
    assert response.success is True
    assert response.optimized_code is not None
    assert "optimized" in response.optimized_code.lower()


@pytest.mark.asyncio
async def test_optimizer_generates_improved_prompt(optimizer_agent):
    """Optimizer generates improved prompts."""
    request = OptimizationRequest(
        skill_name="test_skill",
        current_prompt="Execute the task",
        performance_metrics={"success_rate": 0.65},
        optimization_goal="improve_clarity",
        seed=42
    )
    
    response = await optimizer_agent.optimize_prompt(request)
    
    assert response.success is True
    assert response.optimized_prompt is not None


@pytest.mark.asyncio
async def test_optimizer_deterministic_output(optimizer_agent):
    """Same seed produces same optimization."""
    request1 = OptimizationRequest(
        skill_name="test_skill",
        current_code="def execute(): pass",
        performance_metrics={"success_rate": 0.65},
        optimization_goal="improve",
        seed=42
    )
    
    request2 = OptimizationRequest(
        skill_name="test_skill",
        current_code="def execute(): pass",
        performance_metrics={"success_rate": 0.65},
        optimization_goal="improve",
        seed=42
    )
    
    response1 = await optimizer_agent.optimize_code(request1)
    response2 = await optimizer_agent.optimize_code(request2)
    
    assert response1.optimization_id == response2.optimization_id


@pytest.mark.asyncio
async def test_optimizer_respects_policy(optimizer_agent):
    """Optimizer respects policy constraints."""
    mock_policy = MagicMock()
    mock_policy.allows_optimization = MagicMock(return_value=False)
    
    optimizer_agent.policy_engine = mock_policy
    
    request = OptimizationRequest(
        skill_name="restricted_skill",
        current_code="def execute(): pass",
        performance_metrics={"success_rate": 0.65},
        optimization_goal="improve",
        seed=42
    )
    
    response = await optimizer_agent.optimize_code(request)
    
    assert response.success is False
    assert "policy" in response.error.lower()


@pytest.mark.asyncio
async def test_optimizer_audit_logs(optimizer_agent):
    """Optimizer logs optimization attempts."""
    audit_log = []
    
    def mock_audit(event):
        audit_log.append(event)
    
    optimizer_agent.audit_logger = MagicMock(record=mock_audit)
    
    request = OptimizationRequest(
        skill_name="test_skill",
        current_code="def execute(): pass",
        performance_metrics={"success_rate": 0.65},
        optimization_goal="improve",
        seed=42
    )
    
    await optimizer_agent.optimize_code(request)
    
    assert len(audit_log) > 0


def test_optimization_request_protocol_version():
    """OptimizationRequest has protocol_version."""
    request = OptimizationRequest(
        skill_name="test",
        current_code="",
        performance_metrics={},
        optimization_goal="improve",
        seed=42
    )
    
    assert request.protocol_version == "1.0"


def test_optimization_response_protocol_version():
    """OptimizationResponse has protocol_version."""
    response = OptimizationResponse(
        success=True,
        optimization_id="test-id"
    )
    
    assert response.protocol_version == "1.0"
