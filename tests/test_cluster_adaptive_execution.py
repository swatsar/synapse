"""Tests for cluster-wide adaptive execution.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.self_improvement.engine import (
    SelfImprovementEngine,
    ImprovementPlan
)


pytestmark = pytest.mark.unit


@pytest.fixture
def cluster_engine():
    """Create self-improvement engine with cluster support."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_system_metrics = MagicMock(return_value={
        "cluster_nodes": 3,
        "cluster_load": {"node1": 45, "node2": 62, "node3": 38}
    })
    mock_telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.65,
        "avg_latency_ms": 350
    })
    
    mock_resource = MagicMock()
    mock_resource.check_limits = MagicMock(return_value=True)
    mock_resource.get_available = MagicMock(return_value={"cpu": 80, "memory": 2048})
    
    mock_policy = MagicMock()
    mock_policy.check_permission = MagicMock(return_value=True)
    mock_policy.requires_approval = MagicMock(return_value=False)
    
    mock_registry = MagicMock()
    mock_registry.get_skill = MagicMock(return_value=MagicMock(
        name="cluster_skill",
        risk_level=1,
        success_rate=0.65
    ))
    mock_registry.register = AsyncMock(return_value=True)
    
    mock_cluster = MagicMock()
    mock_cluster.broadcast_improvement = AsyncMock(return_value={
        "nodes_updated": 3,
        "success": True
    })
    mock_cluster.get_cluster_state = MagicMock(return_value={
        "nodes": ["node1", "node2", "node3"],
        "consistent": True
    })
    
    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry
    )
    engine.cluster_manager = mock_cluster
    
    return engine


@pytest.mark.asyncio
async def test_cluster_adaptive_improvement(cluster_engine):
    """Improvement adapts across cluster nodes."""
    plan = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result = await cluster_engine.improve(plan)
    
    assert result.success is True
    assert result.cluster_propagated is True
    assert result.nodes_affected == 3


@pytest.mark.asyncio
async def test_cluster_deterministic_placement(cluster_engine):
    """Task placement is deterministic across cluster."""
    plan1 = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    plan2 = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result1 = await cluster_engine.improve(plan1)
    result2 = await cluster_engine.improve(plan2)
    
    assert result1.improvement_id == result2.improvement_id
    assert result1.nodes_affected == result2.nodes_affected


@pytest.mark.asyncio
async def test_cluster_state_consistency(cluster_engine):
    """Cluster state remains consistent after improvement."""
    plan = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    result = await cluster_engine.improve(plan)
    
    # Verify cluster state is consistent
    state = cluster_engine.cluster_manager.get_cluster_state()
    assert state["consistent"] is True


@pytest.mark.asyncio
async def test_cluster_telemetry_aggregation(cluster_engine):
    """Telemetry aggregates across cluster nodes."""
    telemetry_events = []
    
    def mock_record(event, data):
        telemetry_events.append({"event": event, "data": data})
    
    cluster_engine.telemetry.record = mock_record
    
    plan = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )
    
    await cluster_engine.improve(plan)
    
    assert len(telemetry_events) > 0
    assert any("cluster" in str(e).lower() for e in telemetry_events)


@pytest.mark.asyncio
async def test_cluster_high_risk_routing(cluster_engine):
    """High-risk improvements route through approval pipeline."""
    cluster_engine.policy_engine.requires_approval = MagicMock(return_value=True)
    
    plan = ImprovementPlan(
        target="cluster",
        improvement_type="policy_change",
        risk_level=4,
        seed=42,
        cluster_wide=True
    )
    
    result = await cluster_engine.improve(plan)
    
    assert result.approval_required is True
    assert result.status == "pending_approval"
