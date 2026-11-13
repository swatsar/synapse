"""API contracts for adapter rollback and background training jobs."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from synapse.api.app import app


def _adapter(model: Path, name: str, *, promoted: bool = True) -> Path:
    root = model.parent.parent / "adapters" / name
    root.mkdir(parents=True)
    (root / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": str(model)}), encoding="utf-8"
    )
    (root / "training_manifest.json").write_text(
        json.dumps(
            {
                "base_model": str(model),
                "promotion_status": "promoted" if promoted else "rejected",
                "holdout_loss_before": 2.0,
                "holdout_loss_after": 1.5,
                "steps": 4,
                "records": 12,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_adapter_history_and_rollback_endpoints(monkeypatch, tmp_path):
    from synapse.api.routes import training as training_route

    model = tmp_path / ".synapse" / "models" / "base"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    older = _adapter(model, "older")
    newer = _adapter(model, "newer")
    import os

    stamp = older.stat().st_mtime - 120
    os.utime(older, (stamp, stamp))

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(training_route, "_active_model_path", lambda: str(model))
    monkeypatch.setattr(training_route, "_clear_adapter_cache", lambda: None)

    with TestClient(app) as client:
        history = client.get("/api/v1/training/adapters")
        assert history.status_code == 200
        payload = history.json()
        assert {row["name"] for row in payload["adapters"]} == {"older", "newer"}
        assert payload["selected"] == str(newer.resolve())
        assert payload["pinned"] is None

        activated = client.post("/api/v1/training/adapters/older/activate")
        assert activated.status_code == 200
        payload = activated.json()
        assert payload["pinned"] == "older"
        assert payload["selected"] == str(older.resolve())
        rows = {row["name"]: row for row in payload["adapters"]}
        assert rows["older"]["pinned"] is True
        assert rows["older"]["selected"] is True
        assert rows["newer"]["selected"] is False

        automatic = client.post("/api/v1/training/adapters/auto")
        assert automatic.status_code == 200
        payload = automatic.json()
        assert payload["pinned"] is None
        assert payload["selected"] == str(newer.resolve())

        assert client.post("/api/v1/training/adapters/missing/activate").status_code == 404


def test_rejected_adapter_cannot_be_pinned(monkeypatch, tmp_path):
    from synapse.api.routes import training as training_route

    model = tmp_path / ".synapse" / "models" / "base"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    _adapter(model, "rejected", promoted=False)

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(training_route, "_active_model_path", lambda: str(model))
    monkeypatch.setattr(training_route, "_clear_adapter_cache", lambda: None)

    with TestClient(app) as client:
        response = client.post("/api/v1/training/adapters/rejected/activate")
    assert response.status_code == 409


def test_async_training_job_reports_progress_and_cancels(monkeypatch, tmp_path):
    import threading

    from synapse.api.routes import training as training_route

    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    snapshot = SimpleNamespace(snapshot_id="ds_test", manifest_hash="manifest-hash")
    started = threading.Event()

    class FakeStore:
        def close(self):
            pass

    def fake_train_lora(**kwargs):
        assert kwargs["metadata"]["origin"] == "api_job"
        kwargs["progress_callback"]({"phase": "training", "step": 1, "steps": 3, "loss": 1.5})
        started.set()
        while not kwargs["should_cancel"]():
            time.sleep(0.01)
        return SimpleNamespace(
            to_dict=lambda: {
                "status": "cancelled",
                "error": "cancelled_by_operator",
                "promotion_status": "not_promoted",
                "run_id": "train_fake",
                "protocol_version": "1.0",
            }
        )

    fake_network = SimpleNamespace(record_execution=lambda **kwargs: None, consolidate=lambda: None)

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(training_route, "_resolve_model", lambda model_id: str(model))
    monkeypatch.setattr(
        training_route, "_snapshots",
        lambda: SimpleNamespace(load=lambda snapshot_id: snapshot),
    )
    monkeypatch.setattr(training_route, "_experience_store", lambda: FakeStore())
    monkeypatch.setattr(training_route, "train_lora", fake_train_lora)
    monkeypatch.setattr(training_route, "get_growth_network", lambda workspace: fake_network)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/training/runs",
            json={
                "model_id": "test/model",
                "snapshot_id": "ds_test",
                "steps": 3,
                "max_length": 64,
                "require_gpu": False,
            },
        )
        assert response.status_code == 202, response.text
        job = response.json()["job"]
        run_id = job["run_id"]
        assert job["status"] in {"queued", "running"}
        assert started.wait(5.0)

        # A second concurrent job is refused instead of queueing another 27 GB run.
        duplicate = client.post(
            "/api/v1/training/runs",
            json={"model_id": "test/model", "snapshot_id": "ds_test", "steps": 1, "require_gpu": False},
        )
        assert duplicate.status_code == 409

        cancelled = client.post(f"/api/v1/training/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["cancelled"] is True

        deadline = time.monotonic() + 10
        final = None
        while time.monotonic() < deadline:
            current = client.get(f"/api/v1/training/runs/{run_id}")
            assert current.status_code == 200
            final = current.json()["job"]
            if final["status"] in {"cancelled", "completed", "failed", "blocked"}:
                break
            time.sleep(0.02)

        assert final is not None
        assert final["status"] == "cancelled", final
        assert final["cancel_requested"] is True
        assert final["progress"]["phase"] == "done"
        persisted = json.loads(
            (tmp_path / ".synapse" / "training_runs" / f"{run_id}.json").read_text(
                encoding="utf-8"
            )
        )
        assert persisted["status"] == "cancelled"

        missing = client.get("/api/v1/training/runs/trainjob_missing")
        assert missing.status_code == 404
