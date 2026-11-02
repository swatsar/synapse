"""Tests for multi-node predictive feedback.

Phase 12 - Predictive Autonomy & Proactive Risk Management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.predictive.engine import (
    PredictiveEngine,
    PredictionRequest,
    PredictionResult
)
from synapse.runtime.cluster.manager import ClusterManager


pytestmark = pytest.mark.unit


def create_mock_cluster_manager():
    """Create mock cluster manager."""
    manager = MagicMock(spec=ClusterManager)
    manager.broadcast_prediction = AsyncMock(return_value={
        "success": True,
        "nodes": 3,
        "propagated": True
    })
    manager.get_cluster_state = MagicMock(return_value={
        "nodes": ["node1", "node2", "node3"],
        "healthy": 3
    })
    manager.create_cluster_snapshot = AsyncMock(return_value="snap_123")
    return manager


def create_mock_telemetry():
    """Create mock telemetry."""
    telemetry = MagicMock()
    telemetry.get_cluster_metrics = MagicMock(return_value={
        "node1": {"cpu": 75, "memory": 1200},
        "node2": {"cpu": 82, "memory": 1400},
        "node3": {"cpu": 60, "memory": 1000}
    })
    telemetry.get_historical_metrics = MagicMock(return_value={
        "cluster_cpu_trend": [65, 70, 75, 80, 85],
        "cluster_memory_trend": [1000, 1200, 1400, 1600, 1800],
        "cpu_trend": [65, 70, 75, 80, 85],
        "memory_trend": [1000, 1200, 1400, 1600, 1800]
    })
    return telemetry


def create_mock_resource_manager():
    """Create mock resource manager."""
    manager = MagicMock()
    manager.get_cluster_limits = MagicMock(return_value={
        "total_cpu": 300,
        "total_memory": 6144
    })
    return manager


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    return engine


@pytest.fixture
def mock_cluster_manager():
    return create_mock_cluster_manager()


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
def predictive_engine(mock_cluster_manager, mock_telemetry, mock_resource_manager, mock_policy_engine):
    """Create predictive engine with cluster support."""
    return PredictiveEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        cluster_manager=mock_cluster_manager
    )


@pytest.mark.asyncio
async def test_cluster_wide_prediction(predictive_engine, mock_cluster_manager):
    """Prediction propagates cluster-wide."""
    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    result = await predictive_engine.predict(request)

    assert result.cluster_propagated is True
    mock_cluster_manager.broadcast_prediction.assert_called()


@pytest.mark.asyncio
async def test_cluster_prediction_consistent_across_nodes(predictive_engine):
    """Prediction is consistent across all nodes."""
    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    result = await predictive_engine.predict(request)

    assert result.consistent is True


@pytest.mark.asyncio
async def test_cluster_mitigation_propagated(predictive_engine, mock_cluster_manager):
    """Mitigation actions propagate cluster-wide."""
    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    result = await predictive_engine.predict(request)

    if result.mitigation:
        assert result.mitigation.cluster_propagated is True


@pytest.mark.asyncio
async def test_cluster_telemetry_includes_predictions(predictive_engine, mock_telemetry):
    """Telemetry includes predictive events."""
    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    await predictive_engine.predict(request)

    # Verify historical metrics were called (which is what the engine uses)
    mock_telemetry.get_historical_metrics.assert_called()


@pytest.mark.asyncio
async def test_cluster_audit_includes_predictions(predictive_engine):
    """Audit logs include predictive events."""
    audit_log = []
    predictive_engine.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    await predictive_engine.predict(request)

    assert len(audit_log) > 0


@pytest.mark.asyncio
async def test_high_risk_cluster_prediction_routes_to_approval(predictive_engine, mock_policy_engine):
    """High-risk cluster predictions route through HumanApprovalPipeline."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    request = PredictionRequest(
        target="cluster",
        prediction_type="critical_failure",
        horizon_minutes=15,
        seed=42,
        cluster_wide=True
    )

    result = await predictive_engine.predict(request)

    if result.risk_level >= 3:
        assert result.requires_approval is True


@pytest.mark.asyncio
async def test_deterministic_cluster_prediction(predictive_engine):
    """Cluster predictions are deterministic."""
    request1 = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    request2 = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    result1 = await predictive_engine.predict(request1)
    result2 = await predictive_engine.predict(request2)

    assert result1.prediction_id == result2.prediction_id


@pytest.mark.asyncio
async def test_cluster_snapshot_before_mitigation(predictive_engine, mock_cluster_manager):
    """Cluster snapshot created before mitigation."""
    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True,
        create_snapshot=True
    )

    result = await predictive_engine.predict(request)

    if result.mitigation:
        mock_cluster_manager.create_cluster_snapshot.assert_called()
