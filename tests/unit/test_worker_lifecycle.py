"""Worker subprocesses must not outlive the server that owns them."""
from __future__ import annotations

import asyncio
import os
import pickle
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from synapse.runtime.worker_backend import (
    IsolatedWorkerBackend,
    _WORKER_RUNNER_CODE,
)


@pytest.mark.asyncio
async def test_cancelled_worker_is_terminated(tmp_path):
    """Server shutdown/cancellation must kill the isolated child process."""
    pid_file = tmp_path / "worker.pid"
    source = f"""
import os
import time
from pathlib import Path

def handler():
    Path({str(pid_file)!r}).write_text(str(os.getpid()))
    time.sleep(30)
    return {{"success": True}}
"""
    task = asyncio.create_task(
        IsolatedWorkerBackend().run_skill(
            "cancel_test", source, isolation_level="subprocess",
        )
    )
    for _ in range(200):
        if pid_file.exists():
            break
        await asyncio.sleep(0.05)
    assert pid_file.exists(), "worker did not start"
    worker_pid = int(pid_file.read_text(encoding="utf-8"))

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(100):
        if not psutil.pid_exists(worker_pid):
            break
        await asyncio.sleep(0.05)
    assert not psutil.pid_exists(worker_pid), "cancelled worker was left running"


def test_worker_exits_when_parent_process_disappears(tmp_path):
    """A force-killed server must not leave an orphaned training worker."""
    repo_root = Path(__file__).resolve().parents[2]
    dummy_parent = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(2.0)"],
    )
    runner = tmp_path / "runner.py"
    runner.write_text(_WORKER_RUNNER_CODE, encoding="utf-8")
    payload_path = tmp_path / "payload.pkl"
    payload = {
        "target_type": "source",
        "source_code": (
            "import time\n"
            "def handler():\n"
            "    time.sleep(30)\n"
            "    return {'success': True}\n"
        ),
        "params": {},
        "context_data": {
            "session_id": "test",
            "agent_id": "test",
            "trace_id": "test",
            "capabilities": [],
            "workspace_root": str(repo_root),
        },
        "isolation_type": "subprocess",
        "parent_pid": dummy_parent.pid,
    }
    payload_path.write_bytes(pickle.dumps(payload))
    env = IsolatedWorkerBackend._build_clean_env()
    proc = subprocess.Popen(
        [sys.executable, "-I", "-B", str(runner), str(payload_path)],
        cwd=tmp_path,
        env=env,
    )
    try:
        dummy_parent.wait(timeout=10)
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if dummy_parent.poll() is None:
            dummy_parent.kill()
            dummy_parent.wait()
    assert proc.returncode != 0, "orphaned worker kept running after parent exit"
