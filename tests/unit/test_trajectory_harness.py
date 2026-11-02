"""
Unit tests for TrajectoryHarness (deepseek-ai/deepseek-harness integration).
"""

import json
import pytest
from pathlib import Path
from synapse.harnesses.trajectory import TrajectoryHarness, PROTOCOL_VERSION


@pytest.fixture
def harness(tmp_path):
    return TrajectoryHarness(storage_dir=tmp_path)


def test_protocol_version(harness):
    traj_id = harness.start_trajectory("task_1", "sess_1", "Test trajectory recording")
    record = harness.finish_trajectory(traj_id, success=True)
    assert record.protocol_version == PROTOCOL_VERSION


def test_record_multistep_trajectory(harness):
    traj_id = harness.start_trajectory("task_123", "sess_456", "Refactor module", model="claude-sonnet-5-5")
    harness.record_step(
        traj_id,
        stage="PERCEIVE",
        thought="User requests refactoring of database connector",
    )
    harness.record_step(
        traj_id,
        stage="ACT",
        action={"tool": "read_file", "params": {"file": "db.py"}},
        observation="File content retrieved",
    )
    harness.record_step(
        traj_id,
        stage="EVALUATE",
        evaluation={"score": 100, "status": "completed"},
    )

    record = harness.finish_trajectory(traj_id, success=True, duration_ms=120.5)
    assert record is not None
    assert record.total_steps == 3
    assert record.success is True
    assert record.duration_ms == 120.5
    assert len(record.steps) == 3


def test_export_dataset_jsonl(harness, tmp_path):
    traj_id = harness.start_trajectory("task_sft", "sess_sft", "SFT training run")
    harness.record_step(traj_id, stage="PLAN", thought="Step by step execution")
    harness.finish_trajectory(traj_id, success=True)

    jsonl_path = tmp_path / "dataset.jsonl"
    exported_count = harness.export_dataset_jsonl(jsonl_path)
    assert exported_count == 1
    assert jsonl_path.exists()

    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["objective"] == "SFT training run"
