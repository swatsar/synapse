"""End-to-end tests for the production task-execution path."""
import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from synapse.api.app import app, lifespan
from synapse.core.models import SkillManifest
from synapse.core.orchestrator import build_orchestrator
from synapse.skills.dynamic.registry import SkillRegistry
from synapse.security.capability_manager import CapabilityManager


@pytest.fixture
def configured_app(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    monkeypatch.setenv("SYNAPSE_DB_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("SYNAPSE_VECTOR_DIR", str(tmp_path / "vectors"))
    monkeypatch.setenv("SYNAPSE_BACKUP_DIR", str(tmp_path / "backups"))
    (tmp_path / "workspace").mkdir()
    (tmp_path / "workspace" / "smoke.txt").write_text("real file content", encoding="utf-8")
    with TestClient(app) as client:
        yield client, tmp_path


def test_factory_reads_file_and_rejects_workspace_escape(configured_app):
    client, root = configured_app
    outside = root / "secret.txt"
    outside.write_text("do not expose", encoding="utf-8")

    success = client.post(
        "/api/v1/tasks", json={"task": "Read a file", "payload": {"path": "smoke.txt"}},
    )
    assert success.status_code == 200
    assert success.json()["status"] == "completed", success.json()
    assert success.json()["result"]["action_result"]["outputs"][0]["content"] == "real file content"
    assert success.json()["result"]["invocation_receipt"]["action_type"] == "task"
    assert success.json()["result"]["invocation_receipt"]["run_id"]

    denied = client.post(
        "/api/v1/tasks", json={"task": "Read a file", "payload": {"path": str(outside)}},
    )
    assert denied.json()["status"] == "failed"
    assert "outside the workspace" in json.dumps(denied.json())

    unknown = client.post("/api/v1/tasks", json={"task": "An entirely unsupported action"})
    assert unknown.json()["status"] == "failed"
    assert unknown.json()["success"] is False


def test_approval_is_private_and_retries_with_server_authorization(configured_app):
    client, _ = configured_app
    runtime = client.app.state.orchestrator

    class HighRiskSkill:
        async def execute(self, ctx, **params):
            return {"success": True, "approval_granted": ctx.approval_granted}

    registry = SkillRegistry(capability_manager=CapabilityManager())
    registry.register_builtin(
        SkillManifest(name="code_generator", risk_level=3, trust_level="verified"),
        HighRiskSkill(),
    )
    runtime.skill_registry = registry
    runtime.planner.skill_registry = registry
    runtime.security_manager = None

    bypass = client.post("/api/v1/tasks", json={
        "task": "Generate code", "approval_granted": True, "_approval_granted": True,
    })
    assert bypass.status_code == 422

    pending = client.post("/api/v1/tasks", json={"task": "Generate code"})
    assert pending.json()["status"] == "approval_required"
    approval_id = pending.json()["approval_id"]

    approved = client.post(f"/api/v1/approvals/{approval_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    retry = next(t for t in client.get("/api/v1/tasks").json()["tasks"] if t["id"] == approved.json()["execution_task_id"])
    assert retry["status"] == "failed", retry
    assert "container isolation backend is not available" in retry["error"]
    assert client.post(f"/api/v1/approvals/{approval_id}/approve").status_code == 409


def test_dashboard_static_resources_and_real_backup(configured_app):
    client, root = configured_app
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Synapse" in dashboard.text
    assert "unsafe-inline" not in dashboard.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200

    created = client.post("/api/v1/settings/backup")
    assert created.status_code == 200, created.text
    backup_id = created.json()["backup_id"]
    backup_file = root / "backups" / f"{backup_id}.sqlite3"
    assert backup_file.stat().st_size > 0
    with sqlite3.connect(backup_file) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"short_term", "long_term", "episodic"} <= tables
    assert client.post(f"/api/v1/settings/restore/{backup_id}").status_code == 501


def test_agents_report_embedded_components(configured_app):
    client, _ = configured_app
    response = client.get("/api/v1/agents/planner")
    assert response.status_code == 200
    assert response.json()["status"] == "embedded"
    assert client.post("/api/v1/agents/planner/start").status_code == 501


def test_websocket_rejects_missing_credentials_and_accepts_valid_json(monkeypatch):
    monkeypatch.setenv("SYNAPSE_API_KEY", "local-test-key")
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws"):
                pass
        with client.websocket_connect("/ws?token=local-test-key") as socket:
            socket.send_text(json.dumps({"ping": True}))
            assert socket.receive_json()["data"] == {"ping": True}
            socket.send_text("not json")
            assert socket.receive_json()["type"] == "error"
