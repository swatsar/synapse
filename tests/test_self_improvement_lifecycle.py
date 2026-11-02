"""Tests for self-improvement lifecycle.

Phase 11 - Continuous Self-Improvement & Adaptive Governance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.self_improvement.engine import (
    SelfImprovementEngine,
    ImprovementPlan,
    ImprovementResult
)


pytestmark = pytest.mark.unit


def create_mock_telemetry():
    """Create mock telemetry engine with proper return values."""
    telemetry = MagicMock()
    telemetry.get_skill_metrics = MagicMock(return_value={
        "success_rate": 0.72,
        "avg_latency_ms": 420,
        "resource_usage": {"cpu": 75, "memory": 1536}
    })
    telemetry.get_system_metrics = MagicMock(return_value={
        "failure_rate": 0.12,
        "throughput": 150,
        "success_rate": 0.72
    })
    return telemetry


def create_mock_resource_manager():
    """Create mock resource manager."""
    manager = MagicMock()
    manager.check_limits = MagicMock(return_value=True)
    manager.get_available = MagicMock(return_value={
        "cpu": 80,
        "memory": 2048
    })
    return manager


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    engine.update_policy = AsyncMock(return_value=True)
    return engine


def create_mock_skill_registry():
    """Create mock skill registry."""
    registry = MagicMock()
    registry.get_skill = MagicMock(return_value=MagicMock(
        name="test_skill",
        risk_level=1,
        success_rate=0.72
    ))
    registry.register = AsyncMock(return_value=True)
    return registry


@pytest.fixture
def mock_telemetry():
    return create_mock_telemetry()


@pytest.fixture
def mock_resource_manager():
    return create_mock_resource_manager()


@pytest.fixture
def mock_policy_engine():
    return create_mock_policy_engine()


@pytest.fixture
def mock_skill_registry():
    return create_mock_skill_registry()


@pytest.fixture
def self_improvement_engine(mock_telemetry, mock_resource_manager, mock_policy_engine, mock_skill_registry):
    """Create self-improvement engine."""
    return SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        skill_registry=mock_skill_registry,
        rollback_manager=MagicMock(),
        audit_logger=MagicMock(record=lambda e: None)
    )


@pytest.mark.asyncio
async def test_self_improvement_analyzes_metrics(self_improvement_engine):
    """Self-improvement analyzes telemetry metrics."""
    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await self_improvement_engine.improve(plan)

    assert result is not None
    assert result.analysis is not None
    assert result.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_self_improvement_low_risk_autonomous(self_improvement_engine):
    """Low-risk improvements execute autonomously."""
    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await self_improvement_engine.improve(plan)

    assert result.success is True
    assert result.approval_required is False


@pytest.mark.asyncio
async def test_self_improvement_high_risk_requires_approval(self_improvement_engine):
    """High-risk improvements require approval."""
    plan = ImprovementPlan(
        target="critical_skill",
        improvement_type="security",
        risk_level=4,
        seed=42
    )

    result = await self_improvement_engine.improve(plan)

    assert result.approval_required is True
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_self_improvement_deterministic(self_improvement_engine):
    """Same seed produces same improvement result."""
    plan1 = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    plan2 = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result1 = await self_improvement_engine.improve(plan1)
    result2 = await self_improvement_engine.improve(plan2)

    assert result1.improvement_id == result2.improvement_id


@pytest.mark.asyncio
async def test_self_improvement_audit_logged(self_improvement_engine):
    """Self-improvement events are audit logged."""
    audit_log = []
    self_improvement_engine.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    await self_improvement_engine.improve(plan)

    assert len(audit_log) > 0


def test_improvement_plan_protocol_version():
    """ImprovementPlan has protocol_version."""
    plan = ImprovementPlan(
        target="test",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )
    assert plan.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_self_improvement_with_no_telemetry(mock_resource_manager, mock_policy_engine, mock_skill_registry):
    """Self-improvement works without telemetry."""
    engine = SelfImprovementEngine(
        telemetry=None,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        skill_registry=mock_skill_registry
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_with_no_resource_manager(mock_telemetry, mock_policy_engine, mock_skill_registry):
    """Self-improvement works without resource manager."""
    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=None,
        policy_engine=mock_policy_engine,
        skill_registry=mock_skill_registry
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_with_no_skill_registry(mock_telemetry, mock_resource_manager, mock_policy_engine):
    """Self-improvement works without skill registry."""
    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        skill_registry=None
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_cluster_without_manager(mock_telemetry, mock_resource_manager, mock_policy_engine, mock_skill_registry):
    """Self-improvement cluster-wide without cluster manager."""
    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        skill_registry=mock_skill_registry,
        cluster_manager=None
    )

    plan = ImprovementPlan(
        target="cluster",
        improvement_type="load_balancing",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )

    result = await engine.improve(plan)
    assert result is not None


# Additional tests for coverage
@pytest.mark.asyncio
async def test_self_improvement_without_telemetry():
    """Self-improvement works without telemetry."""
    mock_registry = create_mock_skill_registry()
    mock_policy = create_mock_policy_engine()
    mock_resource = create_mock_resource_manager()

    engine = SelfImprovementEngine(
        telemetry=None,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=MagicMock()
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_without_skill_registry():
    """Self-improvement works without skill registry."""
    mock_policy = create_mock_policy_engine()
    mock_resource = create_mock_resource_manager()
    mock_telemetry = create_mock_telemetry()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=None,
        rollback_manager=MagicMock()
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_without_resource_manager():
    """Self-improvement works without resource manager."""
    mock_registry = create_mock_skill_registry()
    mock_policy = create_mock_policy_engine()
    mock_telemetry = create_mock_telemetry()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=None,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=MagicMock()
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_without_rollback_manager():
    """Self-improvement works without rollback manager."""
    mock_registry = create_mock_skill_registry()
    mock_policy = create_mock_policy_engine()
    mock_telemetry = create_mock_telemetry()
    mock_resource = create_mock_resource_manager()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=None
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result is not None


@pytest.mark.asyncio
async def test_self_improvement_resource_exceeded():
    """Self-improvement handles resource exceeded."""
    mock_resource = MagicMock()
    mock_resource.check_limits = MagicMock(return_value=False)
    mock_resource.get_available = MagicMock(return_value={})

    mock_policy = create_mock_policy_engine()
    mock_telemetry = create_mock_telemetry()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=MagicMock(),
        rollback_manager=MagicMock()
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result.success is False


@pytest.mark.asyncio
async def test_self_improvement_registration_failure():
    """Self-improvement handles registration failure."""
    mock_registry = MagicMock()
    mock_registry.register = AsyncMock(return_value=False)

    mock_rollback = MagicMock()
    mock_rollback.create_checkpoint = AsyncMock(return_value="cp-123")
    mock_rollback.execute_rollback = AsyncMock(return_value=MagicMock(success=True))

    mock_policy = create_mock_policy_engine()
    mock_telemetry = create_mock_telemetry()
    mock_resource = create_mock_resource_manager()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=mock_rollback
    )

    plan = ImprovementPlan(
        target="skill:test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42
    )

    result = await engine.improve(plan)
    assert result.success is False
    assert result.rollback_executed is True


@pytest.mark.asyncio
async def test_self_improvement_cluster_wide():
    """Self-improvement cluster-wide coordination."""
    mock_cluster = MagicMock()
    # Return correct format with 'success' key
    mock_cluster.broadcast_improvement = AsyncMock(return_value={
        "success": True,
        "nodes": 3
    })

    mock_registry = create_mock_skill_registry()
    mock_policy = create_mock_policy_engine()
    mock_telemetry = create_mock_telemetry()
    mock_resource = create_mock_resource_manager()

    engine = SelfImprovementEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource,
        policy_engine=mock_policy,
        skill_registry=mock_registry,
        rollback_manager=MagicMock(),
        cluster_manager=mock_cluster
    )

    plan = ImprovementPlan(
        target="test_skill",
        improvement_type="performance",
        risk_level=1,
        seed=42,
        cluster_wide=True
    )

    result = await engine.improve(plan)
    assert result.cluster_propagated is True
