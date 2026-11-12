"""The operator training endpoint must report blocked runs, not crash."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from synapse.api.app import app
from synapse.training.locking import TrainingLock


def test_training_run_returns_blocked_evidence_when_lock_is_held(
    monkeypatch, tmp_path,
):
    """Regression: the blocked path omitted base_model_hash and returned 500.

    A second training request must not start another full run while the
    autonomous loop owns the cross-process lock. It must return the normal
    evidence contract with an explicit blocker.
    """
    from synapse.api.routes import training as training_route

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    snapshot = SimpleNamespace(
        snapshot_id="ds_test", manifest_hash="manifest-hash",
    )
    monkeypatch.setattr(training_route, "_resolve_model", lambda model_id: str(model_dir))
    monkeypatch.setattr(
        training_route, "_snapshots",
        lambda: SimpleNamespace(load=lambda snapshot_id: snapshot),
    )

    lock = TrainingLock(tmp_path / ".synapse" / "training.lock")
    assert lock.acquire() is True
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/training/run",
                json={
                    "model_id": "test/model",
                    "snapshot_id": "ds_test",
                    "steps": 1,
                    "max_length": 64,
                    "require_gpu": False,
                },
            )
    finally:
        lock.release()

    assert response.status_code == 200
    evidence = response.json()["training"]
    assert evidence["status"] == "blocked"
    assert evidence["blockers"] == ["training_running_in_another_process"]
    assert evidence["snapshot_id"] == "ds_test"
    assert evidence["snapshot_manifest_hash"] == "manifest-hash"
    assert evidence["base_model_hash"] != ""
    assert evidence["run_id"].startswith("train_")
