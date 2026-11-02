"""
Integration tests for OmniRouter API routes (/api/v1/router/*).

Protocol Version: 1.0
"""

import pytest
from fastapi.testclient import TestClient

PROTOCOL_VERSION = "1.0"


@pytest.fixture
def client():
    from synapse.api.app import app
    with TestClient(app) as c:
        yield c


def test_router_catalog_endpoint(client):
    response = client.get("/api/v1/router/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "catalog" in data
    assert data["total_models"] >= 10
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert any(m["id"] == "claude-sonnet-5-5" for m in data["catalog"])
    assert any(m["id"] == "claude-opus-5-5" for m in data["catalog"])
    assert any(m["id"] == "gpt-4o" for m in data["catalog"])
    assert any(m["id"] == "llama3.2" for m in data["catalog"])


def test_router_health_endpoint(client):
    response = client.get("/api/v1/router/health")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "anthropic" in data["providers"]
    assert "openai" in data["providers"]
    assert "ollama" in data["providers"]
    assert data["protocol_version"] == PROTOCOL_VERSION


def test_router_stats_endpoint(client):
    response = client.get("/api/v1/router/stats")
    assert response.status_code == 200
    data = response.json()
    assert "routed_total" in data
    assert "routes_by_model" in data
    assert data["protocol_version"] == PROTOCOL_VERSION


def test_router_route_coding_task(client):
    response = client.post(
        "/api/v1/router/route",
        json={"task": "def solve_matrix(a, b):\n    import numpy as np\n    return np.linalg.solve(a, b)"},
    )
    assert response.status_code == 200
    data = response.json()
    decision = data["decision"]
    assert decision["detected_domain"] == "coding"
    assert decision["model"] == "claude-sonnet-5-5"
    assert decision["provider"] == "anthropic"
    assert len(decision["fallback_chain"]) > 0


def test_router_route_computer_use_task(client):
    response = client.post(
        "/api/v1/router/route",
        json={"task": "Open browser, navigate to URL and click the submit button"},
    )
    assert response.status_code == 200
    data = response.json()
    decision = data["decision"]
    assert decision["detected_domain"] == "computer_use"
    assert decision["model"] == "claude-sonnet-5-5"
    assert decision["capabilities"]["computer_use"] is True


def test_router_route_local_only_task(client):
    response = client.post(
        "/api/v1/router/route",
        json={
            "task": "Process sensitive documents",
            "requirements": {"local_only": True},
        },
    )
    assert response.status_code == 200
    data = response.json()
    decision = data["decision"]
    assert decision["provider"] == "ollama"
    assert decision["tier"] == "local"
    assert decision["cost_tier"] == "FREE"


def test_router_route_explicit_override(client):
    response = client.post(
        "/api/v1/router/route",
        json={
            "task": "Any task",
            "requirements": {"model": "gpt-4o"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    decision = data["decision"]
    assert decision["model"] == "gpt-4o"
    assert decision["provider"] == "openai"


def test_router_execute_endpoint(client):
    response = client.post(
        "/api/v1/router/execute",
        json={"task": "Quick status test query"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "model_used" in data
    assert "route_decision" in data
    assert data["protocol_version"] == PROTOCOL_VERSION


def test_status_endpoint_includes_router_info(client):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "router" in data
    assert "default_model" in data["router"]
    assert data["router"]["total_models"] >= 10


def test_session_task_records_router_event(client):
    # Create session
    session_res = client.post("/api/v1/sessions", json={"title": "Test Router Session"})
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # Post task
    task_res = client.post(
        f"/api/v1/sessions/{session_id}/tasks",
        json={"task": "def process_data(): return True"},
    )
    assert task_res.status_code == 202

    # Give the background executor a moment or read events
    import time
    time.sleep(0.3)

    events_res = client.get(f"/api/v1/sessions/{session_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()["events"]
    router_events = [e for e in events if e["event"] == "router"]
    assert len(router_events) >= 1
    decision = router_events[0]["data"]
    assert decision["detected_domain"] == "coding"
    assert decision["model"] == "claude-sonnet-5-5"
