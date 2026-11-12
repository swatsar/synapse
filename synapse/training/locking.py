"""Cross-process serialization for real LoRA training runs.

Every caller that invokes :func:`synapse.training.trainer.train_lora` must hold
this lock: the autonomous loop, chat-driven learning and the operator training
endpoint all write adapters and load full checkpoints. Without it two runs can
execute concurrently in the same process, doubling memory and racing over the
adapter directory.

The lock is non-blocking. Callers should report an honest ``blocked`` outcome
instead of queueing an unbounded number of expensive training jobs.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path


class TrainingLock:
    """Exclusive, non-blocking lock around one real training run."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._handle = None
        self._key: str | None = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> bool:
        """Try to take the lock. Returns ``False`` if another run owns it."""
        if self._handle is not None:
            return True
        key = str(self.path)
        with _paths_lock:
            if key in _held_paths:
                return False
        handle = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"lock")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            return False
        with _paths_lock:
            if key in _held_paths:
                try:
                    handle.close()
                except OSError:
                    pass
                return False
            _held_paths.add(key)
        self._handle = handle
        self._key = key
        return True

    def release(self) -> None:
        handle = self._handle
        key = self._key
        self._handle = None
        self._key = None
        if key is not None:
            with _paths_lock:
                _held_paths.discard(key)
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            handle.close()
        except OSError:
            pass

    def is_held_elsewhere(self) -> bool:
        """Probe whether another process (or lock object) owns the lock.

        The probe takes and immediately releases a separate handle, so it does
        not block a real run. ``False`` also means this object already owns the
        lock: a caller checking readiness must not report its own run as an
        external one.
        """
        if self._handle is not None:
            return False
        probe = TrainingLock(self.path)
        if probe.acquire():
            probe.release()
            return False
        return True

    def __enter__(self) -> "TrainingLock":
        if not self.acquire():
            raise RuntimeError("training_running_in_another_process")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


# Process-local registry, complementing the OS file lock for two loops that
# live in the same process (API server owner + chat-driven learning).
_paths_lock = threading.Lock()
_held_paths: set[str] = set()


__all__ = ["TrainingLock"]
