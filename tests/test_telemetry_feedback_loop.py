"""Tests for telemetry feedback loops.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.agents.governor import (
    GovernorAgent,
    GovernanceDecision,
    GovernanceAction
)


pytestmark = pytest.mark.unit


@pytest.fixture
def governor_agent():
    """Create governor agent."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "skill_success_rate": 0.72,
        "avg_latency_ms": 420,
        "resource_utilization": {"cpu": 75, "memory": 1536},
        "failure_rate": 0.12
    })
    mock_telemetry.get_skill_metrics = MagicMock(return_value={
        "skill_a": {"success_rate": 0.65, "latency_ms": 350},
        "skill_b": {"success_rate": 0.85, "latency_ms": 120}
    })
    
    mock_policy = MagicMock()
    mock_policy.update_policy = AsyncMock(return_value=True)
    
    mock_resource = MagicMock()
    mock_resource.adjust_limits = AsyncMock(return_value=True)
    
    return GovernorAgent(
        telemetry=mock_telemetry,
        policy_engine=mock_policy,
        resource_manager=mock_resource,
        audit_logger=MagicMock(record=lambda e: None)
    )


@pytest.mark.asyncio
async def test_governor_analyzes_telemetry(governor_agent):
    """Governor analyzes telemetry data."""
    decision = await governor_agent.analyze()
    
    assert decision is not None
    assert decision.analysis is not None
    assert decision.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_governor_detects_bottlenecks(governor_agent):
    """Governor detects performance bottlenecks."""
    decision = await governor_agent.analyze()
    
    # Should detect skill_a has lower success rate
    assert decision.bottlenecks is not None
    assert len(decision.bottlenecks) > 0


@pytest.mark.asyncio
async def test_governor_proposes_actions(governor_agent):
    """Governor proposes governance actions."""
    decision = await governor_agent.analyze()
    
    assert decision.actions is not None
    assert len(decision.actions) > 0


@pytest.mark.asyncio
async def test_governor_executes_low_risk_actions(governor_agent):
    """Governor executes low-risk actions autonomously."""
    action = GovernanceAction(
        action_type="adjust_resource_limit",
        target="skill_a",
        parameters={"max_cpu": 80},
        risk_level=1,
        seed=42
    )
    
    result = await governor_agent.execute_action(action)
    
    assert result.success is True
    assert result.approval_required is False


@pytest.mark.asyncio
async def test_governor_high_risk_requires_approval(governor_agent):
    """High-risk governance actions require approval."""
    action = GovernanceAction(
        action_type="change_security_policy",
        target="system",
        parameters={"approval_threshold": 2},
        risk_level=4,
        seed=42
    )
    
    result = await governor_agent.execute_action(action)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_governor_feedback_loop(governor_agent):
    """Governor creates feedback loop to optimizer."""
    # Analyze and create feedback
    decision = await governor_agent.analyze()
    
    # Feedback should be recorded
    assert decision.feedback is not None
    assert "optimizer" in decision.feedback or "policy" in decision.feedback


@pytest.mark.asyncio
async def test_governor_audit_logged(governor_agent):
    """Governor actions are audit logged."""
    audit_log = []
    governor_agent.audit_logger = MagicMock(record=lambda e: audit_log.append(e))
    
    await governor_agent.analyze()
    
    assert len(audit_log) > 0


def test_governance_decision_protocol_version():
    """GovernanceDecision has protocol_version."""
    decision = GovernanceDecision(
        analysis={},
        bottlenecks=[],
        actions=[],
        feedback={}
    )
    assert decision.protocol_version == "1.0"


# Additional tests for coverage
@pytest.mark.asyncio
async def test_governor_without_telemetry():
    """Governor works without telemetry."""
    governor = GovernorAgent(
        telemetry=None,
        policy_engine=MagicMock(),
        resource_manager=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    decision = await governor.analyze()
    assert decision is not None
    assert decision.analysis == {"system": {}, "skills": {}}


@pytest.mark.asyncio
async def test_governor_without_policy_engine():
    """Governor works without policy engine."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "failure_rate": 0.15
    })
    
    governor = GovernorAgent(
        telemetry=mock_telemetry,
        policy_engine=None,
        resource_manager=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    decision = await governor.analyze()
    assert decision is not None


@pytest.mark.asyncio
async def test_governor_without_resource_manager():
    """Governor works without resource manager."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={})
    
    governor = GovernorAgent(
        telemetry=mock_telemetry,
        policy_engine=MagicMock(),
        resource_manager=None,
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    action = GovernanceAction(
        action_type="adjust_resource_limit",
        target="test",
        parameters={},
        risk_level=1,
        seed=42
    )
    
    result = await governor.execute_action(action)
    assert result.success is True


@pytest.mark.asyncio
async def test_governor_action_exception():
    """Governor handles action exceptions."""
    mock_resource = MagicMock()
    mock_resource.adjust_limits = AsyncMock(side_effect=Exception("Test error"))
    
    governor = GovernorAgent(
        telemetry=MagicMock(),
        policy_engine=MagicMock(),
        resource_manager=mock_resource,
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    action = GovernanceAction(
        action_type="adjust_resource_limit",
        target="test",
        parameters={},
        risk_level=1,
        seed=42
    )
    
    result = await governor.execute_action(action)
    assert result.success is False
    assert "Test error" in result.error


@pytest.mark.asyncio
async def test_governor_change_security_policy_action():
    """Governor can execute security policy changes."""
    mock_policy = MagicMock()
    mock_policy.update_policy = AsyncMock(return_value=True)
    
    governor = GovernorAgent(
        telemetry=MagicMock(),
        policy_engine=mock_policy,
        resource_manager=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    action = GovernanceAction(
        action_type="change_security_policy",
        target="system",
        parameters={"threshold": 3},
        risk_level=1,
        seed=42
    )
    
    result = await governor.execute_action(action)
    assert result.success is True


@pytest.mark.asyncio
async def test_governor_optimize_skill_action():
    """Governor can execute skill optimization actions."""
    governor = GovernorAgent(
        telemetry=MagicMock(),
        policy_engine=MagicMock(),
        resource_manager=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    action = GovernanceAction(
        action_type="optimize_skill",
        target="skill_a",
        parameters={"focus": "latency"},
        risk_level=1,
        seed=42
    )
    
    result = await governor.execute_action(action)
    assert result.success is True


@pytest.mark.asyncio
async def test_governor_without_audit_logger():
    """Governor works without audit logger."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={})
    
    governor = GovernorAgent(
        telemetry=mock_telemetry,
        policy_engine=MagicMock(),
        resource_manager=MagicMock(),
        audit_logger=None
    )
    
    decision = await governor.analyze()
    assert decision is not None
