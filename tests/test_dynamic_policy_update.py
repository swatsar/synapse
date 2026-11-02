"""Tests for dynamic policy updates.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.policy.adaptive.manager import (
    AdaptivePolicyManager,
    PolicyUpdate,
    PolicyUpdateResult
)


pytestmark = pytest.mark.unit


@pytest.fixture
def policy_manager():
    """Create adaptive policy manager."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "failure_rate": 0.08,
        "resource_utilization": {"cpu": 65}
    })
    
    return AdaptivePolicyManager(
        telemetry=mock_telemetry,
        audit_logger=MagicMock(record=lambda e: None)
    )


@pytest.mark.asyncio
async def test_policy_update_based_on_metrics(policy_manager):
    """Policy updates based on telemetry metrics."""
    update = PolicyUpdate(
        policy_name="resource_limits",
        updates={"max_cpu": 90, "max_memory": 4096},
        reason="High resource utilization detected",
        risk_level=2,
        seed=42
    )
    
    result = await policy_manager.apply_update(update)
    
    assert result.success is True
    assert result.policy_name == "resource_limits"
    assert result.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_high_risk_policy_update_requires_approval(policy_manager):
    """High-risk policy updates require human approval."""
    update = PolicyUpdate(
        policy_name="security_threshold",
        updates={"approval_threshold": 2},
        reason="Lowering security threshold",
        risk_level=4,
        seed=42
    )
    
    result = await policy_manager.apply_update(update)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_policy_update_cluster_wide(policy_manager):
    """Policy updates propagate cluster-wide."""
    mock_cluster = MagicMock()
    mock_cluster.broadcast_policy = AsyncMock(return_value={
        "nodes_updated": 3,
        "success": True
    })
    
    policy_manager.cluster_manager = mock_cluster
    
    update = PolicyUpdate(
        policy_name="task_priority",
        updates={"default_priority": 5},
        reason="Optimizing task scheduling",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result = await policy_manager.apply_update(update)
    
    assert result.cluster_propagated is True
    assert result.nodes_updated == 3


@pytest.mark.asyncio
async def test_policy_update_audit_logged(policy_manager):
    """Policy updates are audit logged."""
    audit_log = []
    policy_manager.audit_logger = MagicMock(record=lambda e: audit_log.append(e))
    
    update = PolicyUpdate(
        policy_name="resource_limits",
        updates={"max_cpu": 90},
        reason="Test update",
        risk_level=1,
        seed=42
    )
    
    await policy_manager.apply_update(update)
    
    assert len(audit_log) > 0
    assert any("policy" in str(e).lower() for e in audit_log)


@pytest.mark.asyncio
async def test_policy_update_deterministic(policy_manager):
    """Same seed produces same policy update result."""
    update1 = PolicyUpdate(
        policy_name="resource_limits",
        updates={"max_cpu": 90},
        reason="Test",
        risk_level=1,
        seed=42
    )
    
    update2 = PolicyUpdate(
        policy_name="resource_limits",
        updates={"max_cpu": 90},
        reason="Test",
        risk_level=1,
        seed=42
    )
    
    result1 = await policy_manager.apply_update(update1)
    result2 = await policy_manager.apply_update(update2)
    
    assert result1.update_id == result2.update_id


def test_policy_update_protocol_version():
    """PolicyUpdate has protocol_version."""
    update = PolicyUpdate(
        policy_name="test",
        updates={},
        reason="test",
        risk_level=1,
        seed=42
    )
    assert update.protocol_version == "1.0"


# Additional tests for coverage
@pytest.mark.asyncio
async def test_policy_update_without_cluster_manager():
    """Policy update works without cluster manager."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={})
    
    manager = AdaptivePolicyManager(
        telemetry=mock_telemetry,
        audit_logger=MagicMock(record=lambda e: None),
        cluster_manager=None
    )
    
    update = PolicyUpdate(
        policy_name="test_policy",
        updates={"key": "value"},
        reason="test",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result = await manager.apply_update(update)
    assert result.success is True
    assert result.cluster_propagated is False


@pytest.mark.asyncio
async def test_policy_get_policy():
    """Get policy returns correct policy."""
    manager = AdaptivePolicyManager(
        telemetry=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    # Apply a policy first
    update = PolicyUpdate(
        policy_name="test_policy",
        updates={"key": "value"},
        reason="test",
        risk_level=1,
        seed=42
    )
    await manager.apply_update(update)
    
    # Get the policy
    policy = manager.get_policy("test_policy")
    assert policy is not None
    assert policy["key"] == "value"


@pytest.mark.asyncio
async def test_policy_get_all_policies():
    """Get all policies returns all policies."""
    manager = AdaptivePolicyManager(
        telemetry=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    # Apply multiple policies
    for i in range(3):
        update = PolicyUpdate(
            policy_name=f"policy_{i}",
            updates={"key": f"value_{i}"},
            reason="test",
            risk_level=1,
            seed=42+i
        )
        await manager.apply_update(update)
    
    policies = manager.get_all_policies()
    assert len(policies) == 3


@pytest.mark.asyncio
async def test_policy_analyze_and_suggest():
    """Analyze and suggest returns suggestions."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "resource_utilization": {"cpu": 75},
        "failure_rate": 0.08
    })
    
    manager = AdaptivePolicyManager(
        telemetry=mock_telemetry,
        audit_logger=MagicMock(record=lambda e: None)
    )
    
    suggestions = await manager.analyze_and_suggest()
    assert "suggestions" in suggestions
    assert len(suggestions["suggestions"]) > 0
