from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app


def test_integrations_inventory_is_truthful():
    with TestClient(app) as client:
        response = client.get("/api/v1/integrations")
    assert response.status_code == 200
    data = response.json()
    assert {item["id"] for item in data["executors"]} == {"codex", "claude_code"}
    assert data["mcp"]["status"] == "registry_available"
    assert data["plugins"]["status"] == "runtime_available"
    assert data["vally"]["status"] == "not_configured"


def test_runtime_info_explains_api_key_scope(monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    with TestClient(app) as client:
        response = client.get("/runtime-info")
    assert response.status_code == 200
    data = response.json()
    assert data["api_auth_required"] is False
    assert "не требуется" in data["api_auth_description"]


def test_plain_chat_request_does_not_fail_capability_bootstrap(monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/tasks", json={"task": "Привет, ответь коротко"})
    assert response.status_code == 200
    assert response.json().get("error") != "Security check failed"
    security = response.json().get("result", {}).get("security_result", {})
    assert "memory:read" not in security.get("issues", [])
    # The generic executor is now a real local-model path; success depends on
    # the downloaded model/runtime, never on a synthetic fallback.
    action = response.json().get("result", {}).get("action_result", {})
    assert action.get("errors", [{}])[0].get("error") != "Active skill not found: generic_executor"
