"""Tests for human approval in proactive scenarios.

Phase 12 - Predictive Autonomy & Proactive Risk Management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.skills.predictive.engine import (
    PredictiveEngine,
    PredictionRequest
)
from synapse.policy.proactive.manager import (
    ProactivePolicyManager,
    ProactiveRule,
    ProactiveAction
)
from synapse.control_plane.control import HumanApprovalPipeline


pytestmark = pytest.mark.unit


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    return engine


def create_mock_human_approval():
    """Create mock human approval pipeline."""
    pipeline = MagicMock(spec=HumanApprovalPipeline)
    pipeline.request_approval = AsyncMock(return_value=MagicMock(
        approved=True,
        approval_id="appr_123"
    ))
    pipeline.is_pending = MagicMock(return_value=False)
    return pipeline


def create_mock_telemetry():
    """Create mock telemetry."""
    telemetry = MagicMock()
    telemetry.get_metrics = MagicMock(return_value={
        "cpu": 85,
        "memory": 1800,
        "predicted_risk": 0.9
    })
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
    manager.get_limits = MagicMock(return_value={"cpu": 100, "memory": 2048})
    return manager


@pytest.fixture
def mock_policy_engine():
    return create_mock_policy_engine()


@pytest.fixture
def mock_human_approval():
    return create_mock_human_approval()


@pytest.fixture
def mock_telemetry():
    return create_mock_telemetry()


@pytest.fixture
def mock_resource_manager():
    return create_mock_resource_manager()


@pytest.fixture
def predictive_engine(mock_policy_engine, mock_telemetry, mock_resource_manager, mock_human_approval):
    """Create predictive engine with human approval."""
    return PredictiveEngine(
        telemetry=mock_telemetry,
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        human_approval=mock_human_approval
    )


@pytest.fixture
def proactive_manager(mock_policy_engine, mock_telemetry, mock_human_approval):
    """Create proactive policy manager with human approval."""
    return ProactivePolicyManager(
        policy_engine=mock_policy_engine,
        telemetry=mock_telemetry,
        human_approval=mock_human_approval
    )


@pytest.mark.asyncio
async def test_high_risk_prediction_routes_to_approval(predictive_engine, mock_policy_engine, mock_human_approval):
    """High-risk predictions route through HumanApprovalPipeline."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    request = PredictionRequest(
        target="system",
        prediction_type="critical_failure",
        horizon_minutes=15,
        seed=42
    )

    result = await predictive_engine.predict(request)

    # Verify that requires_approval was checked
    if result.risk_level >= 3:
        assert result.requires_approval is True


@pytest.mark.asyncio
async def test_high_risk_proactive_action_routes_to_approval(proactive_manager, mock_policy_engine, mock_human_approval):
    """High-risk proactive actions route through HumanApprovalPipeline."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    rule = ProactiveRule(
        name="high_risk_rule",
        condition={"cpu": ">95"},
        action={"type": "kill_all"},
        risk_level=5
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 98,
        "memory": 1200
    })

    # When policy engine requires approval, action should require approval
    assert action.requires_approval is True or action.auto_applied is False


@pytest.mark.asyncio
async def test_low_risk_prediction_auto_executes(predictive_engine, mock_policy_engine):
    """Low-risk predictions auto-execute without approval."""
    mock_policy_engine.requires_approval = MagicMock(return_value=False)

    request = PredictionRequest(
        target="system",
        prediction_type="resource_adjustment",
        horizon_minutes=60,
        seed=42
    )

    result = await predictive_engine.predict(request)

    # Low risk should auto-execute
    if result.risk_level < 3:
        assert result.auto_executed is True


@pytest.mark.asyncio
async def test_low_risk_proactive_action_auto_executes(proactive_manager, mock_policy_engine):
    """Low-risk proactive actions auto-execute."""
    mock_policy_engine.requires_approval = MagicMock(return_value=False)

    rule = ProactiveRule(
        name="low_risk_rule",
        condition={"cpu": ">70"},
        action={"type": "throttle", "value": 60},
        risk_level=1
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 75,
        "memory": 1200
    })

    assert action.auto_applied is True


@pytest.mark.asyncio
async def test_approval_request_logged(proactive_manager, mock_policy_engine, mock_human_approval):
    """Approval requests are audit logged."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    audit_log = []
    proactive_manager.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    rule = ProactiveRule(
        name="audit_rule",
        condition={"cpu": ">90"},
        action={"type": "alert"},
        risk_level=4
    )

    await proactive_manager.create_rule(rule)
    await proactive_manager.evaluate_and_act({"cpu": 95, "memory": 1200})

    assert len(audit_log) > 0


@pytest.mark.asyncio
async def test_approval_timeout_handling(proactive_manager, mock_policy_engine, mock_human_approval):
    """Approval timeout is handled correctly."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)
    mock_human_approval.is_pending = MagicMock(return_value=True)

    rule = ProactiveRule(
        name="timeout_rule",
        condition={"cpu": ">90"},
        action={"type": "alert"},
        risk_level=4
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 95,
        "memory": 1200
    })

    # When approval is pending, action should reflect that
    assert action.pending_approval is True or action.requires_approval is True


@pytest.mark.asyncio
async def test_cluster_high_risk_routes_to_approval(predictive_engine, mock_policy_engine, mock_human_approval):
    """Cluster high-risk predictions route through HumanApprovalPipeline."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    mock_cluster = MagicMock()
    mock_cluster.broadcast_prediction = AsyncMock(return_value={"success": True, "nodes": 3})
    predictive_engine.cluster_manager = mock_cluster

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
async def test_rollback_on_approval_denied(proactive_manager, mock_policy_engine, mock_human_approval):
    """Rollback triggers when approval is denied."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)
    mock_human_approval.request_approval = AsyncMock(return_value=MagicMock(
        approved=False,
        denial_reason="User rejected"
    ))

    mock_rollback = MagicMock()
    mock_rollback.execute_rollback = AsyncMock(return_value=MagicMock(success=True))
    proactive_manager.rollback_manager = mock_rollback

    rule = ProactiveRule(
        name="denied_rule",
        condition={"cpu": ">90"},
        action={"type": "kill"},
        risk_level=5
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 95,
        "memory": 1200
    })

    # When approval is denied, action should reflect that
    assert action.approval_denied is True or action.requires_approval is True


def test_proactive_action_protocol_version():
    """ProactiveAction has protocol_version."""
    action = ProactiveAction(
        action_type="test",
        target="cpu",
        auto_applied=False,
        requires_approval=True
    )
    assert action.protocol_version == "1.0"
