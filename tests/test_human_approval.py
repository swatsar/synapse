"""Tests for Human-in-the-loop Approval Pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_connector_runtime():
    """Mock connector runtime for approval messages."""
    runtime = MagicMock()
    runtime.send_approval_request = AsyncMock(return_value={"sent": True})
    runtime.wait_for_response = AsyncMock(return_value={"approved": True})
    return runtime


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    logger = MagicMock()
    logger.record = MagicMock()
    return logger


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine."""
    engine = MagicMock()
    engine.requires_approval = MagicMock(return_value=True)
    return engine


@pytest.mark.unit
async def test_high_risk_requires_approval(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test high-risk tasks require human approval."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    task = {"name": "delete_files", "risk_level": 4}
    
    result = await pipeline.process(task)
    
    assert result["status"] == "pending_approval"
    mock_connector_runtime.send_approval_request.assert_called()


@pytest.mark.unit
async def test_low_risk_skips_approval(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test low-risk tasks skip approval."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    mock_policy_engine.requires_approval = MagicMock(return_value=False)
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    task = {"name": "read_file", "risk_level": 1}
    
    result = await pipeline.process(task)
    
    assert result["status"] == "approved"


@pytest.mark.unit
async def test_approval_queue_deterministic_order(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test approval queue maintains deterministic order."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    tasks = [
        {"id": "task3", "risk_level": 3, "timestamp": "2024-01-01T12:00:03"},
        {"id": "task1", "risk_level": 3, "timestamp": "2024-01-01T12:00:01"},
        {"id": "task2", "risk_level": 3, "timestamp": "2024-01-01T12:00:02"},
    ]
    
    ordered = pipeline.order_queue(tasks)
    
    assert ordered[0]["id"] == "task1"
    assert ordered[1]["id"] == "task2"
    assert ordered[2]["id"] == "task3"


@pytest.mark.unit
async def test_approval_audit_logged(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test approval decisions are audit logged."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    await pipeline.process({"name": "test", "risk_level": 3})
    
    mock_audit_logger.record.assert_called()


@pytest.mark.unit
async def test_trace_propagation(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test trace ID propagates through approval pipeline."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    task = {"name": "test", "risk_level": 3, "trace_id": "trace_123"}
    
    result = await pipeline.process(task)
    
    assert result["trace_id"] == "trace_123"


@pytest.mark.unit
def test_protocol_version(mock_connector_runtime, mock_audit_logger, mock_policy_engine):
    """Test HumanApprovalPipeline has protocol_version."""
    from synapse.control_plane.control import HumanApprovalPipeline
    
    pipeline = HumanApprovalPipeline(
        connector_runtime=mock_connector_runtime,
        audit_logger=mock_audit_logger,
        policy_engine=mock_policy_engine
    )
    
    assert pipeline.protocol_version == "1.0"
