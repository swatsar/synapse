"""Background training jobs with progress and cooperative cancellation.

``POST /training/run`` is synchronous: a real CPU run takes minutes, blocks the
HTTP request and cannot be stopped. This registry runs the same ``train_lora``
in a daemon thread, persists one JSON document per run under
``.synapse/training_runs`` and exposes progress/cancel semantics.

The registry is intentionally framework-free so it can be unit-tested without
starting the API. A job that was ``running`` when the process died is reported
as ``interrupted`` instead of pretending to still work.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

TERMINAL_STATUSES = {"completed", "failed", "blocked", "cancelled", "interrupted"}

_JOBS_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_CANCEL_EVENTS: dict[str, threading.Event] = {}
# Windows refuses to replace a file that another thread is reading/writing.
# Job state is persisted from the worker thread (progress) and the request
# thread (cancel), so all state-file I/O is serialized and temp names are
# unique per write attempt.
_IO_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TrainingJobs:
    """Persistent, cancellable training job registry for one workspace."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.root = self.workspace_root / ".synapse" / "training_runs"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def _persist(self, job: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(job["run_id"])
        payload = json.dumps(job, indent=2, ensure_ascii=False)
        with _IO_LOCK:
            # A unique temp name prevents two writers (progress + cancel) from
            # clobbering each other's staging file on Windows.
            tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_text(payload, encoding="utf-8")
            try:
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)

    def _load(self, run_id: str) -> dict[str, Any] | None:
        try:
            with _IO_LOCK:
                payload = json.loads(self._path(run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _reconcile(self, job: dict[str, Any] | None) -> dict[str, Any] | None:
        """A persisted running job from a previous process is not running now."""
        if job is None or job.get("status") not in {"queued", "running"}:
            return job
        with _JOBS_LOCK:
            live = job["run_id"] in _JOBS
        if not live:
            job = dict(job)
            job["status"] = "interrupted"
            job["error"] = "training process stopped before the run finished"
            job["completed_at"] = job.get("completed_at") or _now()
            try:
                self._persist(job)
            except OSError:
                pass
        return job

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------
    def get(self, run_id: str) -> dict[str, Any] | None:
        with _JOBS_LOCK:
            job = dict(_JOBS[run_id]) if run_id in _JOBS else None
        if job is None:
            job = self._load(run_id)
        return self._reconcile(job)

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return rows
        for path in self.root.glob("*.json"):
            payload = self._load(path.stem)
            if isinstance(payload, dict) and payload.get("run_id"):
                rows.append(self._reconcile(payload) or payload)
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return rows[: max(1, int(limit))]

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------
    def submit(
        self,
        runner: Callable[[str, threading.Event, Callable[[dict[str, Any]], None]], dict[str, Any]],
        *,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start ``runner`` in a daemon thread and return the queued job.

        ``runner`` receives ``(run_id, cancel_event, progress_callback)`` and
        must return ``{"training": evidence_dict}``. Raising marks the job
        failed with the exception text.
        """
        run_id = f"trainjob_{uuid.uuid4().hex[:12]}"
        job: dict[str, Any] = {
            "run_id": run_id,
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "progress": {"phase": "queued"},
            "cancel_requested": False,
            "request": dict(request or {}),
            "training": None,
            "error": None,
        }
        cancel_event = threading.Event()
        with _JOBS_LOCK:
            _JOBS[run_id] = job
            _CANCEL_EVENTS[run_id] = cancel_event
        self._persist(job)

        def _progress(payload: dict[str, Any]) -> None:
            with _JOBS_LOCK:
                live = _JOBS.get(run_id)
                if live is None:
                    return
                live["progress"] = dict(payload) | {"updated_at": _now()}
                snapshot = dict(live)
            try:
                self._persist(snapshot)
            except OSError:
                # Progress telemetry must never fail a real training run.
                pass

        def _run() -> None:
            with _JOBS_LOCK:
                live = _JOBS.get(run_id)
                if live is None:
                    return
                live["status"] = "running"
                live["started_at"] = _now()
                if cancel_event.is_set():
                    live["cancel_requested"] = True
                snapshot = dict(live)
            self._persist(snapshot)
            result: dict[str, Any] = {}
            try:
                result = runner(run_id, cancel_event, _progress) or {}
                training = result.get("training") or {}
                status = str(training.get("status") or "completed")
                if status not in TERMINAL_STATUSES:
                    status = "completed"
                with _JOBS_LOCK:
                    live = _JOBS.get(run_id)
                    if live is not None:
                        live["training"] = training
                        live["status"] = status
                        live["error"] = training.get("error")
            except Exception as exc:  # a crashed job must be observable
                with _JOBS_LOCK:
                    live = _JOBS.get(run_id)
                    if live is not None:
                        live["status"] = "failed"
                        live["error"] = str(exc)
            finally:
                with _JOBS_LOCK:
                    live = _JOBS.get(run_id)
                    if live is not None:
                        started = live.get("started_at")
                        completed = _now()
                        live["completed_at"] = completed
                        if started:
                            try:
                                from datetime import datetime as _dt

                                delta = _dt.fromisoformat(completed) - _dt.fromisoformat(started)
                                live["duration_seconds"] = round(delta.total_seconds(), 3)
                            except ValueError:
                                pass
                        live["progress"] = dict(live.get("progress") or {}) | {
                            "phase": "done"
                        }
                        snapshot = dict(live)
                    else:
                        snapshot = None
                    _CANCEL_EVENTS.pop(run_id, None)
                if snapshot is not None:
                    try:
                        self._persist(snapshot)
                    except OSError:
                        pass

        thread = threading.Thread(target=_run, name=f"training-{run_id}", daemon=True)
        thread.start()
        return dict(job)

    def cancel(self, run_id: str) -> bool:
        """Request cooperative cancellation. Returns False for unknown/terminal jobs."""
        with _JOBS_LOCK:
            event = _CANCEL_EVENTS.get(run_id)
            live = _JOBS.get(run_id)
            if event is None or live is None:
                return False
            if live.get("status") in TERMINAL_STATUSES:
                return False
            event.set()
            live["cancel_requested"] = True
            snapshot = dict(live)
        try:
            self._persist(snapshot)
        except OSError:
            # The in-memory event is already set; a state-file failure must not
            # turn an accepted cancellation into an HTTP error.
            pass
        return True


__all__ = ["TERMINAL_STATUSES", "TrainingJobs"]
