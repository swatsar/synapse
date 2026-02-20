"""Tests for Agents API.

Following TDD: Write tests first, then implement.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

PROTOCOL_VERSION = "1.0"


@pytest.fixture
def client():
    """Create test client."""
    from synapse.api.app import app
    return TestClient(app)


# === LIST AGENTS ===

@pytest.mark.api
@pytest.mark.tdd
def test_list_agents_returns_list(client):
    """Test listing agents."""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert data["protocol_version"] == PROTOCOL_VERSION


# === GET AGENT ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_agent_by_id(client):
    """Test getting a specific agent."""
    response = client.get("/api/v1/agents/planner")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "status" in data


@pytest.mark.api
@pytest.mark.tdd
def test_get_agent_not_found(client):
    """Test getting a non-existent agent."""
    response = client.get("/api/v1/agents/nonexistent")
    assert response.status_code == 404


# === AGENT STATUS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_agent_status(client):
    """Test getting agent status."""
    response = client.get("/api/v1/agents/planner/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["protocol_version"] == PROTOCOL_VERSION


# === START/STOP AGENT ===

@pytest.mark.api
@pytest.mark.tdd
def test_start_agent(client):
    """Test starting an agent."""
    response = client.post("/api/v1/agents/planner/start")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


@pytest.mark.api
@pytest.mark.tdd
def test_stop_agent(client):
    """Test stopping an agent."""
    response = client.post("/api/v1/agents/planner/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"


# === AGENT LOGS ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_agent_logs(client):
    """Test getting agent logs."""
    response = client.get("/api/v1/agents/planner/logs")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


# === AGENT CONFIG ===

@pytest.mark.api
@pytest.mark.tdd
def test_get_agent_config(client):
    """Test getting agent configuration."""
    response = client.get("/api/v1/agents/planner/config")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data


@pytest.mark.api
@pytest.mark.tdd
def test_update_agent_config(client):
    """Test updating agent configuration."""
    response = client.put("/api/v1/agents/planner/config", json={
        "max_retries": 5,
        "timeout": 60
    })
    assert response.status_code == 200
    data = response.json()
    assert data["config"]["max_retries"] == 5
