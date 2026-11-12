"""HTTP tests for explicit human verification of model answers."""
from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app
from synapse.experience import ExperienceRecord


def _configure(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    monkeypatch.setenv("SYNAPSE_DB_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("SYNAPSE_VECTOR_DIR", str(tmp_path / "vectors"))
    (tmp_path / "workspace").mkdir()


def _seed_task(client, *, task_text="What is 2 + 2?", status="completed"):
    store = client.app.state.workspace_store
    session = store.create_session("feedback")
    task = store.create_task(session["id"], task_text, {})
    store.update_task(
        task["id"], status=status, success=status == "completed",
        completed_at="2026-11-10T00:00:00+00:00",
    )
    return task


def _seed_experience(client, task_id: str, *, answer="The answer to 2 + 2 is 4."):
    store = client.app.state.container.experience_store
    record = ExperienceRecord(
        task_id=task_id,
        run_id="run-feedback",
        objective="What is 2 + 2?",
        executor="orchestrator.handle",
        provider="local_transformers",
        model="local/qwen",
        execution_success=True,
        verifier_passed=None,
        verifier_status="inconclusive",
        eligibility="ineligible",
        feedback={
            "model_backed": True,
            "candidate_training_text": f"User: What is 2 + 2?\nAssistant: {answer}",
        },
    )
    store.append(record)
    return store


def test_human_feedback_promotes_a_real_answer_to_training_evidence(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    with TestClient(app) as client:
        task = _seed_task(client)
        experience = _seed_experience(client, task["id"])

        response = client.post(
            f"/api/v1/tasks/{task['id']}/feedback",
            json={"passed": True, "note": "verified by operator"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["training_eligible"] is True
        record = experience.latest_for_task(task["id"])
        assert record.verified_for_training is True
        assert record.feedback["training_text"].endswith(
            "The answer to 2 + 2 is 4."
        )
        assert [item.task_id for item in experience.list_records(verified_only=True)] == [
            task["id"]
        ]


def test_human_rejection_blocks_training_and_queued_tasks_are_rejected(
    monkeypatch, tmp_path,
):
    _configure(monkeypatch, tmp_path)
    with TestClient(app) as client:
        task = _seed_task(client)
        experience = _seed_experience(client, task["id"])

        queued = _seed_task(client, status="queued")
        queued_response = client.post(
            f"/api/v1/tasks/{queued['id']}/feedback", json={"passed": True},
        )
        assert queued_response.status_code == 409

        response = client.post(
            f"/api/v1/tasks/{task['id']}/feedback",
            json={"passed": False, "note": "incorrect"},
        )
        assert response.status_code == 200
        assert response.json()["training_eligible"] is False
        assert experience.list_records(verified_only=True) == []
        assert client.post(
            "/api/v1/tasks/missing-task/feedback", json={"passed": True},
        ).status_code == 404


def test_feedback_without_experience_record_is_reported(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    with TestClient(app) as client:
        task = _seed_task(client)
        response = client.post(
            f"/api/v1/tasks/{task['id']}/feedback", json={"passed": True},
        )
        assert response.status_code == 404
