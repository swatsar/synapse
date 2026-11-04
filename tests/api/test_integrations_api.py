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
