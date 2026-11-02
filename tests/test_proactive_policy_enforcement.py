"""Tests for proactive policy enforcement.

Phase 12 - Predictive Autonomy & Proactive Risk Management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.policy.proactive.manager import (
    ProactivePolicyManager,
    ProactiveRule
)
from synapse.skills.predictive.engine import PredictiveEngine


pytestmark = pytest.mark.unit


def create_mock_policy_engine():
    """Create mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=False)
    engine.check_violation = MagicMock(return_value=False)
    engine.register_rule = MagicMock(return_value=True)
    return engine


def create_mock_capability_manager():
    """Create mock capability manager."""
    manager = MagicMock()
    manager.check_capabilities = MagicMock(return_value=MagicMock(approved=True))
    return manager


def create_mock_telemetry():
    """Create mock telemetry."""
    telemetry = MagicMock()
    telemetry.get_metrics = MagicMock(return_value={
        "policy_violations_trend": [0, 1, 2, 3, 5],
        "risk_actions_trend": [1, 2, 3, 5, 8]
    })
    return telemetry


@pytest.fixture
def mock_policy_engine():
    return create_mock_policy_engine()


@pytest.fixture
def mock_capability_manager():
    return create_mock_capability_manager()


@pytest.fixture
def mock_telemetry():
    return create_mock_telemetry()


@pytest.fixture
def proactive_manager(mock_policy_engine, mock_capability_manager, mock_telemetry):
    """Create proactive policy manager."""
    return ProactivePolicyManager(
        policy_engine=mock_policy_engine,
        capability_manager=mock_capability_manager,
        telemetry=mock_telemetry
    )


@pytest.mark.asyncio
async def test_predict_policy_violation(proactive_manager):
    """Predict policy violation before it happens."""
    prediction = await proactive_manager.predict_violation({
        "action": "delete_file",
        "target": "/critical/path",
        "user": "test_user"
    })

    assert prediction is not None
    assert "violation_risk" in prediction


@pytest.mark.asyncio
async def test_block_risky_action(proactive_manager, mock_capability_manager):
    """Block predicted risky action."""
    mock_capability_manager.check_capabilities = MagicMock(
        return_value=MagicMock(approved=False, blocked_capabilities=["fs:delete"])
    )

    result = await proactive_manager.evaluate_action({
        "action": "delete_file",
        "target": "/critical",
        "predicted_risk": 0.9
    })

    assert result.blocked is True


@pytest.mark.asyncio
async def test_high_risk_requires_approval(proactive_manager, mock_policy_engine):
    """High-risk predicted actions require approval."""
    mock_policy_engine.requires_approval = MagicMock(return_value=True)

    result = await proactive_manager.evaluate_action({
        "action": "execute_command",
        "command": "rm -rf /",
        "predicted_risk": 0.95
    })

    assert result.requires_approval is True


@pytest.mark.asyncio
async def test_proactive_rule_creation(proactive_manager):
    """Create proactive rule for policy enforcement."""
    rule = ProactiveRule(
        name="block_critical_deletion",
        condition={"action": "delete", "target": "/critical/**"},
        action={"type": "block"},
        risk_level=5
    )

    result = await proactive_manager.create_rule(rule)

    assert result.success is True


@pytest.mark.asyncio
async def test_proactive_rule_audit_logged(proactive_manager):
    """Proactive policy changes are audit logged."""
    audit_log = []
    proactive_manager.audit_logger = MagicMock(record=lambda e: audit_log.append(e))

    rule = ProactiveRule(
        name="audit_test_rule",
        condition={"cpu": ">90"},
        action={"type": "alert"},
        risk_level=2
    )

    await proactive_manager.create_rule(rule)

    assert len(audit_log) > 0


@pytest.mark.asyncio
async def test_cluster_wide_policy_propagation(proactive_manager):
    """Proactive policies propagate cluster-wide."""
    mock_cluster = MagicMock()
    mock_cluster.broadcast_rule = AsyncMock(return_value={"success": True, "nodes": 3})
    proactive_manager.cluster_manager = mock_cluster

    rule = ProactiveRule(
        name="cluster_policy",
        condition={"action": "dangerous"},
        action={"type": "block"},
        risk_level=4,
        cluster_wide=True
    )

    result = await proactive_manager.create_rule(rule)

    assert result.cluster_propagated is True


@pytest.mark.asyncio
async def test_deterministic_policy_evaluation(proactive_manager):
    """Policy evaluation is deterministic."""
    action = {
        "action": "test",
        "predicted_risk": 0.5,
        "seed": 42
    }

    result1 = await proactive_manager.evaluate_action(action)
    result2 = await proactive_manager.evaluate_action(action)

    assert result1.decision == result2.decision


@pytest.mark.asyncio
async def test_telemetry_feedback_loop(proactive_manager, mock_telemetry):
    """Telemetry metrics inform policy decisions."""
    await proactive_manager.evaluate_action({
        "action": "test",
        "predicted_risk": 0.5
    })

    mock_telemetry.get_metrics.assert_called()
