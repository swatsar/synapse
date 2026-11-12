from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app


def test_integrations_inventory_is_truthful(monkeypatch):
    from synapse.integrations import opencode_bridge
    from synapse.integrations.opencode_bridge import opencode_status

    # Pin the quota circuit. Without this, the endpoint and the assertion can
    # run on opposite sides of a cooldown expiry and disagree while the runtime
    # is actually healthy (observed only in the full suite).
    monkeypatch.setattr(
        opencode_bridge, "quota_status",
        lambda: {
            "exhausted": False, "message": None,
            "retry_after_seconds": 0, "reset_at": None,
            "protocol_version": opencode_bridge.PROTOCOL_VERSION,
        },
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/integrations")
    assert response.status_code == 200
    data = response.json()
    assert {item["id"] for item in data["executors"]} == {"codex", "claude_code"}
    assert data["mcp"]["status"] == "registry_available"
    assert data["plugins"]["status"] == "runtime_available"
    # OpenCode is the only model catalog; Velly has been removed as a data
    # source rather than kept as a live compatibility dependency.
    detected = opencode_status()["status"]
    assert data["opencode"]["status"] == detected
    assert data["opencode"]["runtime"] == "opencode"
    assert data["opencode"]["catalog_source"] == "opencode_cli"
    assert "vally" not in data
    assert "legacy_velly" not in data


def test_opencode_payload_does_not_expose_velly_state():
    with TestClient(app) as client:
        response = client.get("/api/v1/integrations/opencode")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "opencode"
    for removed in ("legacy_velly", "workspaces", "chat_config", "app_dir"):
        assert removed not in payload
    assert isinstance(payload.get("agents"), list)
    assert all(agent["id"] in {"codex", "claude_code"} for agent in payload["agents"])


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
    action = response.json().get("result", {}).get("action_result", {}) or {}
    errors = action.get("errors") or []
    if errors:
        assert errors[0].get("error") != "Active skill not found: generic_executor"
