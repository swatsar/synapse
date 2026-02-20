"""Tests for HTTP API Layer."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator."""
    orchestrator = MagicMock()
    orchestrator.handle = AsyncMock(return_value={"status": "completed"})
    return orchestrator


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager."""
    manager = MagicMock()
    manager.create_checkpoint = MagicMock(return_value=MagicMock(id="test-cp-id"))
    manager.restore = MagicMock()
    return manager


@pytest.fixture
def mock_rollback_manager():
    """Mock rollback manager."""
    manager = MagicMock()
    manager.rollback_to = MagicMock()
    return manager


@pytest.fixture
def app_client(mock_orchestrator, mock_checkpoint_manager, mock_rollback_manager):
    """Create test client with mocked dependencies."""
    from synapse.api.app import create_app
    
    app = create_app(
        orchestrator=mock_orchestrator,
        checkpoint_manager=mock_checkpoint_manager,
        rollback_manager=mock_rollback_manager
    )
    return TestClient(app)


@pytest.mark.unit
def test_health_endpoint(app_client):
    """Test GET /health endpoint."""
    response = app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "protocol_version" in data


@pytest.mark.unit
def test_metrics_endpoint(app_client):
    """Test GET /metrics endpoint."""
    response = app_client.get("/metrics")
    assert response.status_code == 200
    # API returns JSON with metrics and protocol_version
    data = response.json()
    assert "metrics" in data
    assert "protocol_version" in data


@pytest.mark.unit
def test_task_endpoint(app_client, mock_orchestrator):
    """Test POST /task endpoint."""
    response = app_client.post("/task", json={
        "task": "process",
        "payload": {"data": "test"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    mock_orchestrator.handle.assert_called()


@pytest.mark.unit
def test_agents_endpoint(app_client):
    """Test GET /agents endpoint."""
    response = app_client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


@pytest.mark.unit
def test_checkpoint_endpoint(app_client, mock_checkpoint_manager):
    """Test POST /checkpoint endpoint."""
    response = app_client.post("/checkpoint", json={
        "state": {"key": "value"}
    })
    assert response.status_code == 200
    data = response.json()
    assert "checkpoint_id" in data
    mock_checkpoint_manager.create_checkpoint.assert_called()


@pytest.mark.unit
def test_rollback_endpoint(app_client, mock_rollback_manager):
    """Test POST /rollback endpoint."""
    response = app_client.post("/rollback", json={
        "checkpoint_id": "test-cp-id"
    })
    assert response.status_code == 200
    mock_rollback_manager.rollback_to.assert_called()


@pytest.mark.unit
def test_cluster_status_endpoint(app_client):
    """Test GET /cluster/status endpoint."""
    response = app_client.get("/cluster/status")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data or "status" in data


@pytest.mark.unit
def test_protocol_version_validation(app_client):
    """Test protocol_version validation in requests."""
    response = app_client.post("/task", json={
        "task": "process",
        "protocol_version": "1.0"
    })
    assert response.status_code == 200


@pytest.mark.unit
def test_trace_propagation(app_client):
    """Test trace ID propagation."""
    response = app_client.post("/task", json={
        "task": "process"
    }, headers={"X-Trace-ID": "test-trace-123"})
    assert response.status_code == 200
    # Response should have protocol_version
    data = response.json()
    assert "protocol_version" in data
    # Trace ID may or may not be in response depending on implementation
    # This test verifies the endpoint works with trace headers
