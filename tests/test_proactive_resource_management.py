"""Tests for proactive resource management.

Phase 12 - Predictive Autonomy & Proactive Risk Management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.policy.proactive.manager import (
    ProactivePolicyManager,
    ProactiveRule,
    ProactiveAction
)


pytestmark = pytest.mark.unit


def create_mock_resource_manager():
    """Create mock resource manager."""
    manager = MagicMock()
    manager.get_limits = MagicMock(return_value={
        "cpu": 100,
        "memory": 2048,
        "disk": 10240,
        "network": 1024
    })
    manager.get_usage = MagicMock(return_value={
        "cpu": 78,
        "memory": 1664,
        "disk": 5120,
        "network": 512
    })
    manager.adjust_limits = MagicMock(return_value={"success": True})
    return manager


def create_mock_telemetry():
    """Create mock telemetry engine."""
    telemetry = MagicMock()
    telemetry.get_metrics = MagicMock(return_value={
        "cpu_trend": "increasing",
        "memory_trend": "increasing",
        "predicted_overload": True
    })
    return telemetry


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    engine.register_rule = MagicMock(return_value=True)
    return engine


@pytest.fixture
def mock_resource_manager():
    return create_mock_resource_manager()


@pytest.fixture
def mock_telemetry():
    return create_mock_telemetry()


@pytest.fixture
def mock_policy_engine():
    return create_mock_policy_engine()


@pytest.fixture
def proactive_manager(mock_resource_manager, mock_telemetry, mock_policy_engine):
    """Create proactive policy manager."""
    return ProactivePolicyManager(
        resource_manager=mock_resource_manager,
        telemetry=mock_telemetry,
        policy_engine=mock_policy_engine
    )


@pytest.mark.asyncio
async def test_proactive_manager_creates_rule(proactive_manager):
    """Proactive manager creates dynamic rules."""
    rule = ProactiveRule(
        name="cpu_throttle",
        condition={"cpu": ">80"},
        action={"type": "throttle", "target": "cpu", "value": 70},
        risk_level=1
    )

    result = await proactive_manager.create_rule(rule)

    assert result.success is True
    assert result.rule_id is not None


@pytest.mark.asyncio
async def test_proactive_manager_prevents_cpu_overload(proactive_manager):
    """Proactive manager prevents CPU overload."""
    action = await proactive_manager.evaluate_and_act({
        "cpu": 85,
        "memory": 1200,
        "predicted_cpu": 95
    })

    assert action is not None
    assert action.action_type in ["throttle", "redistribute", "alert"]


@pytest.mark.asyncio
async def test_proactive_manager_prevents_memory_exhaustion(proactive_manager):
    """Proactive manager prevents memory exhaustion."""
    action = await proactive_manager.evaluate_and_act({
        "cpu": 50,
        "memory": 1900,
        "predicted_memory": 2100
    })

    assert action is not None
    assert action.action_type in ["limit", "gc", "alert"]


@pytest.mark.asyncio
async def test_proactive_manager_low_risk_auto_applied(proactive_manager):
    """Low-risk proactive actions are auto-applied."""
    rule = ProactiveRule(
        name="low_risk_adjustment",
        condition={"cpu": ">70"},
        action={"type": "adjust", "value": 65},
        risk_level=1
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 75,
        "memory": 1200
    })

    assert action.auto_applied is True


@pytest.mark.asyncio
async def test_proactive_manager_high_risk_requires_approval(proactive_manager, mock_policy_engine):
    """High-risk proactive actions require human approval."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    rule = ProactiveRule(
        name="high_risk_action",
        condition={"cpu": ">90"},
        action={"type": "kill", "target": "*"},
        risk_level=5
    )

    await proactive_manager.create_rule(rule)

    action = await proactive_manager.evaluate_and_act({
        "cpu": 95,
        "memory": 1200
    })

    assert action.requires_approval is True


@pytest.mark.asyncio
async def test_proactive_manager_audit_logged(proactive_manager):
    """Proactive actions are audit logged."""
    audit_log = []
    proactive_manager.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    await proactive_manager.evaluate_and_act({
        "cpu": 85,
        "memory": 1200
    })

    assert len(audit_log) > 0


def test_proactive_rule_protocol_version():
    """ProactiveRule has protocol_version."""
    rule = ProactiveRule(
        name="test",
        condition={"cpu": ">80"},
        action={"type": "test"},
        risk_level=1
    )
    assert rule.protocol_version == "1.0"


def test_proactive_action_protocol_version():
    """ProactiveAction has protocol_version."""
    action = ProactiveAction(
        action_type="test",
        target="cpu",
        auto_applied=False
    )
    assert action.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_proactive_manager_cluster_propagation(proactive_manager):
    """Proactive rules propagate cluster-wide."""
    mock_cluster = MagicMock()
    mock_cluster.broadcast_rule = AsyncMock(return_value={"success": True, "nodes": 3})
    proactive_manager.cluster_manager = mock_cluster

    rule = ProactiveRule(
        name="cluster_rule",
        condition={"cpu": ">80"},
        action={"type": "throttle"},
        risk_level=1,
        cluster_wide=True
    )

    result = await proactive_manager.create_rule(rule)

    assert result.cluster_propagated is True


@pytest.mark.asyncio
async def test_proactive_manager_runtime_update(proactive_manager, mock_policy_engine):
    """PolicyEngine updates runtime without restart."""
    rule = ProactiveRule(
        name="runtime_rule",
        condition={"memory": ">1500"},
        action={"type": "gc"},
        risk_level=1
    )

    await proactive_manager.create_rule(rule)

    # Verify policy engine was updated
    mock_policy_engine.register_rule.assert_called()
