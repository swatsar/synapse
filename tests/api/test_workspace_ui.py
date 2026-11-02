"""Regression tests for the durable agent-workspace UI and its real API."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from synapse.api.app import app, lifespan
from synapse.api.workspace_store import WorkspaceStore
from synapse.core.determinism import DeterministicIDGenerator, DeterministicSeedManager
from synapse.core.orchestrator import Orchestrator


@pytest.fixture
def workspace_client(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("SYNAPSE_UI_DB_PATH", str(tmp_path / "ui.sqlite3"))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.txt").write_text("workspace test content", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("private", encoding="utf-8")
    with TestClient(app) as client:
        yield client, tmp_path


def wait_for_task(client, task_id):
    for _ in range(100):
        resp = client.get(f"/api/v1/tasks/{task_id}")
        if resp.status_code == 200:
            task = resp.json()
            if isinstance(task, dict) and task.get("status") not in {"queued", "running"}:
                return task
        time.sleep(0.05)
    pytest.fail("Task did not finish within the polling deadline")


def test_session_task_history_and_real_progress_survive_restart(workspace_client):
    client, _ = workspace_client
    session = client.post("/api/v1/sessions", json={"title": "Чтение документа"})
    assert session.status_code == 201
    session_id = session.json()["id"]
    queued = client.post(f"/api/v1/sessions/{session_id}/tasks", json={
        "task": "Read a file", "payload": {"path": "docs/note.txt"},
    })
    assert queued.status_code == 202
    task = wait_for_task(client, queued.json()["id"])
    assert task["status"] == "completed", task

    history = client.get(f"/api/v1/sessions/{session_id}").json()
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["content"] == "workspace test content"
    events = client.get(f"/api/v1/sessions/{session_id}/events").json()["events"]
    cognitive_steps = {event["event"] for event in events}
    assert {"perceive", "recall", "plan", "security", "act", "observe", "evaluate", "learn"} <= cognitive_steps
    assert client.get(f"/api/v1/sessions/{session_id}/events?after={events[-1]['id']}").json()["events"] == []

    # A new store instance reads the same persisted session, not process memory.
    reopened = WorkspaceStore(client.app.state.workspace_store.path)
    assert reopened.get_session(session_id)["title"] == "Чтение документа"
    assert reopened.get_task(task["id"])["result"]["action_result"]["outputs"][0]["content"] == "workspace test content"

    retried = client.post(f"/api/v1/tasks/{task['id']}/retry")
    assert retried.status_code == 202
    assert retried.json()["parent_task_id"] == task["id"]
    assert wait_for_task(client, retried.json()["id"])["status"] == "completed"


def test_event_polling_does_not_exhaust_mutation_rate_limit(workspace_client):
    client, _ = workspace_client
    session = client.post("/api/v1/sessions").json()
    for _ in range(65):
        response = client.get(f"/api/v1/sessions/{session['id']}/events?after=0")
        assert response.status_code == 200
    assert client.post("/api/v1/sessions").status_code == 201


def test_file_picker_is_bounded_and_sessions_can_be_renamed_and_archived(workspace_client):
    client, root = workspace_client
    listing = client.get("/api/v1/workspace/files").json()
    assert {"path": "docs/note.txt", "name": "note.txt", "is_directory": False} in listing["files"] or any(
        item["path"] == "docs" and item["is_directory"] for item in listing["directories"]
    )
    assert all(not item["name"].startswith(".") for item in listing["files"] + listing["directories"])
    assert client.get("/api/v1/workspace/files", params={"path": ".."}).status_code == 403
    assert client.get("/api/v1/workspace/files", params={"path": str(root.parent)}).status_code == 403

    session = client.post("/api/v1/sessions", json={"title": "Before"}).json()
    renamed = client.patch(f"/api/v1/sessions/{session['id']}", json={"title": "After"})
    assert renamed.json()["title"] == "After"
    assert client.delete(f"/api/v1/sessions/{session['id']}").json()["status"] == "archived"
    assert client.get(f"/api/v1/sessions/{session['id']}").status_code == 404


@pytest.mark.asyncio
async def test_progress_callbacks_are_isolated_between_concurrent_tasks():
    first, second = [], []
    runtime = Orchestrator(DeterministicSeedManager(), DeterministicIDGenerator())

    async def execute(event, target):
        target.append("before")
        result = await runtime.execute_cycle({"task": event["task"], "_progress_callback": event["callback"]})
        target.append("after")
        return result

    async def callback_for(target):
        async def callback(step, data):
            target.append((step, data["status"]))
        return callback

    async def run(task, target):
        callback = await callback_for(target)
        return await execute({"task": task, "callback": callback}, target)

    await asyncio.gather(run("first", first), run("second", second))
    first_steps = [item for item in first if isinstance(item, tuple)]
    second_steps = [item for item in second if isinstance(item, tuple)]
    assert first_steps == second_steps
    assert len(first_steps) == 16  # Eight cognitive stages: start + finish.
    assert first[:2] == ["before", ("perceive", "running")]
    assert first[-2:] == [("learn", "completed"), "after"]
