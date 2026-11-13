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

_DEFAULT_HEARTBEAT_INTERVAL = 5.0
# A process that stops heartbeating for this long is treated as dead. The
# interval is well below the threshold so normal disk stalls do not create a
# false "interrupted" verdict.
_DEFAULT_STALE_AFTER = 30.0

_JOBS_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_CANCEL_EVENTS: dict[str, threading.Event] = {}
_WATCH_STOPS: dict[str, threading.Event] = {}
_WATCHERS: dict[str, threading.Thread] = {}
# Windows refuses to replace a file that another thread is reading/writing.
# Job state is persisted from the worker thread (progress) and the request
# thread (cancel), so all state-file I/O is serialized and temp names are
# unique per write attempt.
_IO_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TrainingJobs:
    """Persistent, cancellable training job registry for one workspace."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        heartbeat_interval: float = _DEFAULT_HEARTBEAT_INTERVAL,
        stale_after: float = _DEFAULT_STALE_AFTER,
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.root = self.workspace_root / ".synapse" / "training_runs"
        self.heartbeat_interval = max(0.01, float(heartbeat_interval))
        self.stale_after = max(self.heartbeat_interval * 2, float(stale_after))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def _cancel_path(self, run_id: str) -> Path:
        """Cross-process cancellation marker.

        The owning process polls this file and sets its in-memory event. A
        follower process cannot reach that event directly, so the marker is
        the transport between API processes sharing one workspace.
        """
        return self.root / f"{run_id}.cancel"

    @staticmethod
    def _age_seconds(value: Any) -> float | None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - parsed).total_seconds())

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
        """Resolve a queued/running job that is not owned by this process.

        Another API process can legitimately own the run. Its watchdog writes
        ``heartbeat_at`` into the same state file; only a stale heartbeat means
        the owning process died and the job is truly interrupted.
        """
        if job is None or job.get("status") not in {"queued", "running"}:
            return job
        run_id = str(job.get("run_id") or "")
        with _JOBS_LOCK:
            live = run_id in _JOBS
        if live:
            return job
        last_seen = job.get("heartbeat_at") or job.get("started_at") or job.get("created_at")
        age = self._age_seconds(last_seen)
        if age is not None and age <= self.stale_after:
            return job
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
        now = _now()
        job: dict[str, Any] = {
            "run_id": run_id,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "progress": {"phase": "queued"},
            "cancel_requested": False,
            "cancel_requested_at": None,
            "heartbeat_at": now,
            "owner_pid": os.getpid(),
            "request": dict(request or {}),
            "training": None,
            "error": None,
        }
        cancel_event = threading.Event()
        stop_event = threading.Event()
        with _JOBS_LOCK:
            _JOBS[run_id] = job
            _CANCEL_EVENTS[run_id] = cancel_event
        try:
            self._persist(job)
        except OSError:
            with _JOBS_LOCK:
                _JOBS.pop(run_id, None)
                _CANCEL_EVENTS.pop(run_id, None)
            raise

        watcher = threading.Thread(
            target=self._watch,
            args=(run_id, cancel_event, stop_event),
            name=f"training-watch-{run_id}",
            daemon=True,
        )
        with _JOBS_LOCK:
            _WATCH_STOPS[run_id] = stop_event
            _WATCHERS[run_id] = watcher
        watcher.start()

        def _progress(payload: dict[str, Any]) -> None:
            with _JOBS_LOCK:
                live = _JOBS.get(run_id)
                if live is None:
                    return
                live["progress"] = dict(payload) | {"updated_at": _now()}
                live["heartbeat_at"] = _now()
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
                live["heartbeat_at"] = live["started_at"]
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
                # Stop the watchdog before writing the terminal snapshot so it
                # cannot persist a stale "running" heartbeat afterwards.
                stop = _WATCH_STOPS.pop(run_id, None)
                if stop is not None:
                    stop.set()
                active_watcher = _WATCHERS.pop(run_id, None)
                if active_watcher is not None and active_watcher is not threading.current_thread():
                    active_watcher.join(timeout=max(0.2, self.heartbeat_interval * 3))
                try:
                    self._cancel_path(run_id).unlink(missing_ok=True)
                except OSError:
                    pass
                with _JOBS_LOCK:
                    live = _JOBS.get(run_id)
                    if live is not None:
                        started = live.get("started_at")
                        completed = _now()
                        live["completed_at"] = completed
                        live["heartbeat_at"] = completed
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

    def _watch(
        self,
        run_id: str,
        cancel_event: threading.Event,
        stop_event: threading.Event,
    ) -> None:
        """Heartbeat and cross-process cancellation for one live job."""
        marker = self._cancel_path(run_id)
        while not stop_event.wait(self.heartbeat_interval):
            try:
                marker_seen = marker.is_file()
            except OSError:
                marker_seen = False
            if marker_seen:
                cancel_event.set()
            with _JOBS_LOCK:
                live = _JOBS.get(run_id)
                if live is None:
                    return
                live["heartbeat_at"] = _now()
                if marker_seen:
                    live["cancel_requested"] = True
                    live["cancel_requested_at"] = live.get("cancel_requested_at") or _now()
                snapshot = dict(live)
            try:
                self._persist(snapshot)
            except OSError:
                # A heartbeat failure must not fail the training run.
                pass

    def cancel(self, run_id: str) -> bool:
        """Request cancellation from this or another process.

        Locally owned jobs use the in-memory event. A follower process cannot
        reach that event, so it writes a marker file that the owner's watchdog
        observes. Returns False for unknown, terminal or stale jobs.
        """
        marker = self._cancel_path(run_id)
        marker_payload = json.dumps(
            {"run_id": run_id, "requested_at": _now()}, ensure_ascii=False
        )
        with _JOBS_LOCK:
            event = _CANCEL_EVENTS.get(run_id)
            live = _JOBS.get(run_id)
            if event is not None and live is not None:
                if live.get("status") in TERMINAL_STATUSES:
                    return False
                event.set()
                live["cancel_requested"] = True
                live["cancel_requested_at"] = live.get("cancel_requested_at") or _now()
                live["heartbeat_at"] = _now()
                snapshot = dict(live)
                local = True
            else:
                snapshot = None
                local = False

        if local:
            try:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(marker_payload, encoding="utf-8")
            except OSError:
                pass
            try:
                self._persist(snapshot)
            except OSError:
                # The in-memory event is already set; a state-file failure must
                # not turn an accepted cancellation into an HTTP error.
                pass
            return True

        # Follower path: reconcile first so a dead owner is reported as
        # interrupted instead of accepting a cancellation nobody will consume.
        job = self._reconcile(self._load(run_id))
        if job is None or job.get("status") in TERMINAL_STATUSES:
            return False
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(marker_payload, encoding="utf-8")
        except OSError:
            return False
        updated = dict(job)
        updated["cancel_requested"] = True
        updated["cancel_requested_at"] = _now()
        try:
            self._persist(updated)
        except OSError:
            # The marker is the real transport; the owner will still cancel.
            pass

        # The owner may have completed between the reconcile and the marker.
        final = self._load(run_id)
        if final is not None and final.get("status") in TERMINAL_STATUSES:
            try:
                marker.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True


__all__ = ["TERMINAL_STATUSES", "TrainingJobs"]
