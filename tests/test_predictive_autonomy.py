"""Tests for predictive autonomy.

Phase 12 - Predictive Autonomy & Proactive Risk Management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.predictive.engine import (
    PredictiveEngine,
    PredictionRequest,
    PredictionResult
)


pytestmark = pytest.mark.unit


def create_mock_telemetry():
    """Create mock telemetry engine."""
    telemetry = MagicMock()
    telemetry.get_historical_metrics = MagicMock(return_value={
        "cpu_trend": [45, 52, 58, 65, 72, 78],
        "memory_trend": [1024, 1152, 1280, 1408, 1536, 1664],
        "failure_trend": [0.02, 0.03, 0.05, 0.07, 0.10, 0.12]
    })
    telemetry.get_current_metrics = MagicMock(return_value={
        "cpu": 78,
        "memory": 1664,
        "failure_rate": 0.12
    })
    return telemetry


def create_mock_resource_manager():
    """Create mock resource manager."""
    manager = MagicMock()
    manager.get_limits = MagicMock(return_value={
        "cpu": 100,
        "memory": 2048
    })
    manager.get_available = MagicMock(return_value={
        "cpu": 22,
        "memory": 384
    })
    return manager


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    return engine


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
def predictive_engine(mock_telemetry, mock_resource_manager, mock_policy_engine):
    """Create predictive engine."""
    return PredictiveEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine
    )


@pytest.mark.asyncio
async def test_predictive_engine_analyzes_trends(predictive_engine):
    """Predictive engine analyzes historical trends."""
    request = PredictionRequest(
        target="system",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42
    )

    result = await predictive_engine.predict(request)

    assert result is not None
    assert result.predictions is not None
    assert result.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_predictive_engine_detects_cpu_overload(predictive_engine):
    """Predictive engine detects CPU overload risk."""
    request = PredictionRequest(
        target="cpu",
        prediction_type="overload",
        horizon_minutes=15,
        seed=42
    )

    result = await predictive_engine.predict(request)

    assert result is not None
    assert any(p["type"] == "cpu_overload" for p in result.predictions)


@pytest.mark.asyncio
async def test_predictive_engine_detects_memory_exhaustion(predictive_engine):
    """Predictive engine detects memory exhaustion risk."""
    request = PredictionRequest(
        target="memory",
        prediction_type="exhaustion",
        horizon_minutes=30,
        seed=42
    )

    result = await predictive_engine.predict(request)

    assert result is not None
    assert any(p["type"] == "memory_exhaustion" for p in result.predictions)


@pytest.mark.asyncio
async def test_predictive_engine_detects_skill_failure(predictive_engine):
    """Predictive engine detects skill failure risk."""
    request = PredictionRequest(
        target="skill:critical_skill",
        prediction_type="failure",
        horizon_minutes=60,
        seed=42
    )

    result = await predictive_engine.predict(request)

    assert result is not None
    assert result.risk_level >= 0


@pytest.mark.asyncio
async def test_predictive_engine_deterministic(predictive_engine):
    """Same seed produces same prediction."""
    request1 = PredictionRequest(
        target="system",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42
    )

    request2 = PredictionRequest(
        target="system",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42
    )

    result1 = await predictive_engine.predict(request1)
    result2 = await predictive_engine.predict(request2)

    assert result1.prediction_id == result2.prediction_id


@pytest.mark.asyncio
async def test_predictive_engine_audit_logged(predictive_engine):
    """Predictions are audit logged."""
    audit_log = []
    predictive_engine.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    request = PredictionRequest(
        target="system",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42
    )

    await predictive_engine.predict(request)

    assert len(audit_log) > 0


def test_prediction_request_protocol_version():
    """PredictionRequest has protocol_version."""
    request = PredictionRequest(
        target="test",
        prediction_type="test",
        horizon_minutes=30,
        seed=42
    )
    assert request.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_predictive_engine_without_telemetry():
    """Predictive engine works without telemetry."""
    engine = PredictiveEngine(
        telemetry=None,
        resource_manager=create_mock_resource_manager(),
        policy_engine=create_mock_policy_engine()
    )

    request = PredictionRequest(
        target="system",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42
    )

    result = await engine.predict(request)
    assert result is not None


@pytest.mark.asyncio
async def test_predictive_engine_cluster_wide():
    """Predictive engine cluster-wide coordination."""
    mock_cluster = MagicMock()
    mock_cluster.broadcast_prediction = AsyncMock(return_value={"success": True, "nodes": 3})

    engine = PredictiveEngine(
        telemetry=create_mock_telemetry(),
        resource_manager=create_mock_resource_manager(),
        policy_engine=create_mock_policy_engine(),
        cluster_manager=mock_cluster
    )

    request = PredictionRequest(
        target="cluster",
        prediction_type="resource_overload",
        horizon_minutes=30,
        seed=42,
        cluster_wide=True
    )

    result = await engine.predict(request)
    assert result.cluster_propagated is True
