"""
Integration tests for Platform Tools & Integrations API (/api/v1/platform/*).
"""

import pytest
from fastapi.testclient import TestClient
from synapse.api.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_platform_skills_catalog(client):
    res = client.get("/api/v1/platform/skills/catalog")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 4
    skill_ids = [s["id"] for s in data["skills"]]
    assert "security_scan" in skill_ids
    assert "memory_recall" in skill_ids
    assert "model_route" in skill_ids


def test_platform_security_audit(client):
    res = client.post("/api/v1/platform/security/audit", json={"target_dir": "synapse/security"})
    assert res.status_code == 200
    data = res.json()
    assert "score" in data
    assert "grade" in data
    assert data["grade"] in {"A+", "A", "B", "C", "F"}


def test_platform_memory_lifecycle(client):
    # 1. Create
    create_res = client.post(
        "/api/v1/platform/memory/entries",
        json={
            "title": "API Test Note",
            "content": "Verify that memory lifecycle works through HTTP",
            "memory_type": "project",
            "tags": ["api", "test"],
        },
    )
    assert create_res.status_code == 200
    mem_id = create_res.json()["created"]["id"]

    # 2. Search
    search_res = client.get("/api/v1/platform/memory/entries?q=lifecycle")
    assert search_res.status_code == 200
    assert any(e["id"] == mem_id for e in search_res.json()["entries"])

    # 3. Delete
    del_res = client.delete(f"/api/v1/platform/memory/entries/{mem_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True


def test_platform_slash_command(client):
    res = client.post("/api/v1/platform/slash/execute", json={"command": "/help"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "available_commands" in data["output"]


def test_platform_benchmark_run(client):
    res = client.post("/api/v1/platform/benchmarks/run", json={"suite_id": "api_test_suite"})
    assert res.status_code == 200
    data = res.json()
    assert data["suite_id"] == "api_test_suite"
    assert "pass_rate" in data


def test_platform_trajectory_sft_and_dpo_exports(client):
    res_sft = client.get("/api/v1/platform/trajectories/export/sft?format=chatml")
    assert res_sft.status_code == 200
    data_sft = res_sft.json()
    assert data_sft["format"] == "chatml"
    assert "samples" in data_sft

    res_dpo = client.get("/api/v1/platform/trajectories/export/dpo")
    assert res_dpo.status_code == 200
    data_dpo = res_dpo.json()
    assert "pairs" in data_dpo


def test_platform_browser_status_and_execution(client):
    res_status = client.get("/api/v1/platform/browser/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "ready"
    assert "allowed_domains" in status_data

    # Execute safe action
    res_action = client.post("/api/v1/platform/browser/execute", json={
        "action": "screenshot",
    })
    assert res_action.status_code == 200
    action_data = res_action.json()
    assert action_data["action"] == "screenshot"
    assert action_data["status"] == "success"


def test_platform_learning_patterns_and_optimize_prompts(client):
    res_patterns = client.get("/api/v1/platform/learning/patterns")
    assert res_patterns.status_code == 200
    patterns = res_patterns.json()
    assert "low_performing_skills" in patterns

    res_opt = client.post("/api/v1/platform/learning/optimize-prompts", json={
        "agent_name": "developer",
    })
    assert res_opt.status_code == 200
    opt_data = res_opt.json()
    assert opt_data["agent"] == "developer"
    assert "suggestion" in opt_data

