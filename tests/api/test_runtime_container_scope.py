"""The runtime container must follow the active workspace, not the first one."""
from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app
from synapse.runtime import container as container_module
from synapse.runtime.container import RuntimeContainer


def test_lifespan_rebinds_a_stale_container_to_the_active_workspace(
    monkeypatch, tmp_path,
):
    """Regression: a deleted test workspace leaked into later task execution.

    The global container owns the durable work database and the experience
    store. Reusing it after ``SYNAPSE_WORKSPACE_ROOT`` changed made real tasks
    fail with a database path from an already removed directory.
    """
    stale = RuntimeContainer(workspace_root=tmp_path / "stale-workspace")
    container_module.set_runtime_container(stale)

    workspace = tmp_path / "active-workspace"
    workspace.mkdir()
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("SYNAPSE_DB_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("SYNAPSE_VECTOR_DIR", str(tmp_path / "vectors"))
    try:
        with TestClient(app) as client:
            active = client.app.state.container
            assert active is not stale
            assert active.workspace_root == workspace.resolve()
            assert active.experience_store.db_path.startswith(
                str(workspace.resolve())
            )
    finally:
        container_module.set_runtime_container(stale)
