"""Background training jobs: progress, persistence and cooperative cancel."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from synapse.training.jobs import TrainingJobs


def _wait(jobs: TrainingJobs, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = jobs.get(run_id)
        if job and job.get("status") in {"completed", "failed", "blocked", "cancelled", "interrupted"}:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {run_id} did not finish: {jobs.get(run_id)}")


def test_job_runs_reports_progress_and_persists(tmp_path):
    jobs = TrainingJobs(tmp_path)

    def runner(run_id, cancel_event, progress):
        assert run_id.startswith("trainjob_")
        progress({"phase": "training", "step": 1, "steps": 2, "loss": 1.25})
        progress({"phase": "training", "step": 2, "steps": 2, "loss": 1.10})
        return {"training": {"status": "completed", "run_id": run_id, "final_loss": 1.10}}

    queued = jobs.submit(runner, request={"model_id": "test/model"})
    assert queued["status"] in {"queued", "running"}
    final = _wait(jobs, queued["run_id"])

    assert final["status"] == "completed"
    assert final["training"]["final_loss"] == 1.10
    assert final["progress"]["phase"] == "done"
    assert final["duration_seconds"] is not None

    persisted = json.loads(
        (tmp_path / ".synapse" / "training_runs" / f"{queued['run_id']}.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["status"] == "completed"
    assert jobs.list()[0]["run_id"] == queued["run_id"]


def test_cancel_is_cooperative_and_terminal(tmp_path):
    jobs = TrainingJobs(tmp_path)
    started = threading.Event()

    def runner(run_id, cancel_event, progress):
        started.set()
        progress({"phase": "training", "step": 1, "steps": 5})
        while not cancel_event.is_set():
            time.sleep(0.01)
        return {"training": {"status": "cancelled", "error": "cancelled_by_operator"}}

    queued = jobs.submit(runner)
    assert started.wait(2.0)
    assert jobs.cancel(queued["run_id"]) is True
    final = _wait(jobs, queued["run_id"])

    assert final["status"] == "cancelled"
    assert final["cancel_requested"] is True
    assert final["error"] == "cancelled_by_operator"
    assert jobs.cancel(queued["run_id"]) is False


def _write_job(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_follower_reports_live_job_and_cancels_via_marker(tmp_path):
    """A second API process must see a live job and cancel it by marker."""
    from datetime import UTC, datetime

    runs_dir = tmp_path / ".synapse" / "training_runs"
    run_id = "trainjob_remote_live"
    now = datetime.now(UTC).isoformat()
    _write_job(runs_dir / f"{run_id}.json", {
        "run_id": run_id,
        "status": "running",
        "created_at": now,
        "started_at": now,
        "heartbeat_at": now,
        "cancel_requested": False,
        "progress": {"phase": "training"},
    })

    follower = TrainingJobs(tmp_path, stale_after=30)
    job = follower.get(run_id)
    assert job is not None
    assert job["status"] == "running"

    assert follower.cancel(run_id) is True
    marker = runs_dir / f"{run_id}.cancel"
    assert marker.is_file()
    persisted = json.loads((runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    assert persisted["cancel_requested"] is True


def test_stale_remote_job_is_interrupted_and_not_cancellable(tmp_path):
    runs_dir = tmp_path / ".synapse" / "training_runs"
    run_id = "trainjob_remote_stale"
    _write_job(runs_dir / f"{run_id}.json", {
        "run_id": run_id,
        "status": "running",
        "created_at": "2026-01-01T00:00:00+00:00",
        "started_at": "2026-01-01T00:00:01+00:00",
    })

    jobs = TrainingJobs(tmp_path, stale_after=30)
    job = jobs.get(run_id)
    assert job is not None
    assert job["status"] == "interrupted"
    assert jobs.cancel(run_id) is False
    assert not (runs_dir / f"{run_id}.cancel").exists()


def test_owner_observes_external_cancel_marker(tmp_path):
    """The owning process consumes the follower's marker and stops the runner."""
    jobs = TrainingJobs(tmp_path, heartbeat_interval=0.02, stale_after=1.0)
    started = threading.Event()

    def runner(run_id, cancel_event, progress):
        started.set()
        while not cancel_event.is_set():
            time.sleep(0.01)
        return {"training": {"status": "cancelled", "error": "cancelled_by_operator"}}

    queued = jobs.submit(runner)
    assert started.wait(2.0)
    marker = tmp_path / ".synapse" / "training_runs" / f"{queued['run_id']}.cancel"
    marker.write_text(
        json.dumps({"run_id": queued["run_id"], "requested_at": "external"}),
        encoding="utf-8",
    )

    final = _wait(jobs, queued["run_id"])
    assert final["status"] == "cancelled"
    assert final["cancel_requested"] is True
    assert not marker.exists()


def test_crashed_job_is_failed_not_stuck(tmp_path):
    jobs = TrainingJobs(tmp_path)

    def runner(run_id, cancel_event, progress):
        raise RuntimeError("allocator exploded")

    queued = jobs.submit(runner)
    final = _wait(jobs, queued["run_id"])
    assert final["status"] == "failed"
    assert "allocator exploded" in final["error"]


def test_orphaned_running_job_is_reported_as_interrupted(tmp_path):
    jobs = TrainingJobs(tmp_path)
    runs_dir = tmp_path / ".synapse" / "training_runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "trainjob_dead.json").write_text(
        json.dumps(
            {
                "run_id": "trainjob_dead",
                "status": "running",
                "created_at": "2026-01-01T00:00:00+00:00",
                "started_at": "2026-01-01T00:00:01+00:00",
                "progress": {"phase": "training"},
            }
        ),
        encoding="utf-8",
    )

    job = jobs.get("trainjob_dead")
    assert job is not None
    assert job["status"] == "interrupted"
    assert "process stopped" in job["error"]
