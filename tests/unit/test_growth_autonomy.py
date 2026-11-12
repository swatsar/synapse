"""Tests for the autonomous self-development cadence."""
from __future__ import annotations

import asyncio

from synapse.growth.autonomy import AutonomyLoop
from synapse.growth.network import GrowthNetwork


def test_autonomy_loop_is_disabled_under_pytest(tmp_path):
    """Automatic weight training must never run during the test suite."""
    loop = AutonomyLoop(tmp_path, growth_network=GrowthNetwork(":memory:"))
    assert loop.auto_train_enabled is False


def test_autonomy_tick_consolidates_after_threshold(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    for index in range(4):
        network.record_execution(task=f"task {index}", skill="skill_a", success=True)

    loop = AutonomyLoop(tmp_path, growth_network=network, interval_seconds=60)
    loop.consolidate_every = 3
    result = asyncio.run(loop.tick())

    assert result["consolidated"] is True
    assert result["consolidation"]["pass"] == 1
    assert loop.status()["last_consolidation_pass"] == 1
    assert (tmp_path / ".synapse" / "autonomy_state.json").is_file()

    # No new events: the next tick must not consolidate again immediately.
    again = asyncio.run(loop.tick())
    assert again["consolidated"] is False
    assert loop.status()["ticks"] == 2


def test_autonomy_training_is_skipped_without_enough_experience(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    loop = AutonomyLoop(tmp_path, growth_network=network)
    loop.auto_train_enabled = True
    loop.train_cooldown = 86_400.0
    loop.min_records = 10

    result = asyncio.run(loop.tick())
    training = result["training"]
    assert training["status"] == "skipped"
    assert training["reason"] == "not_enough_verified_experience"
    assert loop.status()["last_train_status"] == "skipped"
    assert loop.status()["last_train_at"] is None

    # A skip is not a training attempt: it must not start the long cooldown,
    # otherwise newly arriving experience would wait a whole day to be used.
    again = asyncio.run(loop.tick())
    assert again["training"]["status"] == "skipped"
    assert loop.state.get("last_train_attempt") is None


def test_training_readiness_reports_gates_and_unlocks(tmp_path):
    """Readiness must tell the operator exactly what blocks real training."""
    import time

    from synapse.experience import ExperienceRecord, ExperienceStore

    (tmp_path / ".synapse").mkdir()
    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    for index in range(2):
        store.append(ExperienceRecord(
            task_id=f"task-ready-{index}",
            run_id=f"run-ready-{index}",
            executor="fixture",
            execution_success=True,
            verifier_passed=True,
            verifier_status="passed",
            eligibility="eligible",
        ))
    store.close()

    loop = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth.sqlite3")
    )

    readiness = loop.training_readiness()
    assert readiness["verified_records"] == 2
    assert readiness["ready"] is False
    # Automatic training is disabled under pytest; readiness must say so
    # honestly instead of pretending a run could start.
    assert "auto_train_disabled" in readiness["blockers"]

    loop.auto_train_enabled = True
    loop.min_records = 1
    loop.min_new_records = 1
    ready = loop.training_readiness()
    assert ready["ready"] is True
    assert ready["blockers"] == []

    # A completed attempt trains all current records and starts the cooldown.
    loop.state["last_train_verified_records"] = 2
    loop.state["last_train_attempt"] = time.time()
    loop.state["last_train_status"] = "completed"
    cooling = loop.training_readiness()
    assert cooling["ready"] is False
    assert "cooldown" in cooling["blockers"]
    assert cooling["cooldown_remaining_seconds"] > 0


def test_training_readiness_reports_cross_process_lock(tmp_path):
    """A follower must not claim training can start while another process trains."""
    from synapse.experience import ExperienceRecord, ExperienceStore
    from synapse.training.locking import TrainingLock

    (tmp_path / ".synapse").mkdir()
    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="task-lock-ready",
        run_id="run-lock-ready",
        executor="fixture",
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    ))
    store.close()

    loop = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth.sqlite3")
    )
    loop.auto_train_enabled = True
    loop.min_records = 1
    loop.min_new_records = 1
    assert loop.training_readiness()["ready"] is True

    holder = TrainingLock(tmp_path / ".synapse" / "training.lock")
    assert holder.acquire() is True
    try:
        locked = loop.training_readiness()
        assert locked["ready"] is False
        assert "training_already_running" in locked["blockers"]
    finally:
        holder.release()

    # The same loop reports readiness again once the external run releases it.
    assert loop.training_readiness()["ready"] is True


def test_autonomy_manual_tick_runs_without_automatic_training(tmp_path):
    network = GrowthNetwork(tmp_path / "growth.sqlite3")
    loop = AutonomyLoop(tmp_path, growth_network=network)
    result = asyncio.run(loop.tick())
    assert result["training"] is None
    assert result["auto_train_enabled"] is False


def test_autonomy_loop_process_ownership_is_exclusive(tmp_path):
    """Two server processes must not consolidate/train the same workspace."""
    network_one = GrowthNetwork(tmp_path / "growth.sqlite3")
    network_two = GrowthNetwork(tmp_path / "growth.sqlite3")
    owner = AutonomyLoop(tmp_path, growth_network=network_one)
    follower = AutonomyLoop(tmp_path, growth_network=network_two)

    assert owner._acquire_process_lock() is True
    try:
        result = asyncio.run(follower.tick())
        assert result["skipped"] == "autonomy_owned_by_another_process"
        assert follower.status()["process_role"] == "follower"
    finally:
        owner._release_process_lock()

    # After the owner exits the follower can take over.
    result = asyncio.run(follower.tick())
    assert "skipped" not in result
    assert follower.status()["process_role"] == "owner"
    follower._release_process_lock()


def test_training_lock_serializes_runs_across_processes(tmp_path):
    """Automatic ticks in one process and manual runs in another never overlap."""
    first = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth-one.sqlite3")
    )
    second = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth-two.sqlite3")
    )
    assert first._acquire_training_lock() is True
    try:
        result = asyncio.run(second._maybe_train(force=True))
        assert result == {
            "status": "skipped",
            "reason": "training_running_in_another_process",
        }
    finally:
        first._release_training_lock()

    # Manual training works once the other run releases its lock.
    second.auto_train_enabled = True
    second._train_once = lambda: {"status": "completed", "verified_records": 1}
    result = asyncio.run(second._maybe_train(force=True))
    assert result["status"] == "completed"


def test_training_lock_blocks_a_real_second_process(tmp_path):
    """The file lock, not only the in-process registry, must exclude a run.

    Regression: the old lock test used two loop objects in one process, which
    could pass via the process-local set even if the OS file lock was broken.
    Real training also runs in isolated worker processes, so this must hold
    across process boundaries.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    from synapse.training.locking import TrainingLock

    repo_root = Path(__file__).resolve().parents[2]
    lock_path = tmp_path / "training.lock"
    child_code = (
        "import sys\n"
        "from synapse.training.locking import TrainingLock\n"
        "print(TrainingLock(sys.argv[1]).acquire())\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    ).rstrip(os.pathsep)

    def child_acquire() -> str:
        completed = subprocess.run(
            [sys.executable, "-c", child_code, str(lock_path)],
            cwd=repo_root, env=env, capture_output=True, text=True, timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    holder = TrainingLock(lock_path)
    assert holder.acquire() is True
    try:
        assert child_acquire() == "False"
    finally:
        holder.release()

    assert child_acquire() == "True"


def test_manual_training_is_allowed_on_a_follower_process(tmp_path, monkeypatch):
    """Operator control must work on either API process without stealing cadence."""
    import time

    from synapse.experience import ExperienceStore

    (tmp_path / ".synapse").mkdir()
    ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3").close()

    owner = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth-one.sqlite3")
    )
    follower = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth-two.sqlite3")
    )
    follower.auto_train_enabled = True
    follower.state["last_train_attempt"] = time.time()

    def fake_train():
        return {
            "status": "completed",
            "verified_records": 16,
            "holdout_loss_before": 1.0,
            "holdout_loss_after": 0.5,
            "promotion_status": "promoted",
            "behavioral_probes": 3,
            "behavioral_gate": "no_behavioral_regression",
            "adapter_path": str(tmp_path / "adapter"),
        }

    monkeypatch.setattr(follower, "_train_once", fake_train)

    assert owner._acquire_process_lock() is True
    try:
        result = asyncio.run(follower.train_now(force=True))
        assert result["training"]["status"] == "completed"
        assert result["training"]["behavioral_probes"] == 3
        # The manual action must not silently become the cadence owner.
        assert follower._owner is False
        assert follower.status()["last_train_status"] == "completed"
    finally:
        owner._release_process_lock()


def test_owner_save_preserves_newer_manual_training_evidence(tmp_path):
    """A follower's completed run must not be overwritten by the owner's snapshot."""
    import json

    owner = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth.sqlite3")
    )
    owner.state["last_train_attempt"] = 100.0
    owner.state["last_train_status"] = "skipped"
    owner._save_state()

    path = tmp_path / ".synapse" / "autonomy_state.json"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    persisted.update({
        "last_train_attempt": 200.0,
        "last_train_at": "2026-11-11T00:00:00+00:00",
        "last_train_status": "completed",
        "last_train_verified_records": 55,
        "last_train_result": {"status": "completed", "adapter_path": "a"},
    })
    path.write_text(json.dumps(persisted), encoding="utf-8")

    owner._save_state()
    merged = json.loads(path.read_text(encoding="utf-8"))
    assert merged["last_train_status"] == "completed"
    assert merged["last_train_verified_records"] == 55
    assert merged["last_train_result"]["adapter_path"] == "a"
