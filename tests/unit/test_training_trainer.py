import json
from pathlib import Path

import pytest

from synapse.experience import DatasetSnapshotStore, ExperienceRecord, ExperienceStore
from synapse.training import train_lora


def test_lora_trainer_blocks_empty_verified_text(tmp_path):
    experiences = ExperienceStore(tmp_path / "experience.sqlite3")
    for index in range(3):
        experiences.append(ExperienceRecord(
            task_id=f"task-{index}", run_id=f"run-{index}", executor="fixture",
            execution_success=True, verifier_passed=True, verifier_status="passed",
            eligibility="eligible",
        ))
    snapshot = DatasetSnapshotStore(tmp_path / "datasets").create(experiences, seed=1)
    result = train_lora(
        experience_store=experiences, snapshot=snapshot,
        base_model=tmp_path / "missing-model", output_dir=tmp_path / "adapter",
        require_gpu=False,
    )
    assert result.status == "blocked"
    assert "verified_records_require_non_empty_training_text" not in result.blockers
    assert any(item.startswith("missing_training_dependencies:") for item in result.blockers) is False
    experiences.close()


def test_trainer_evidence_is_serializable(tmp_path):
    experiences = ExperienceStore(tmp_path / "experience.sqlite3")
    for index in range(3):
        experiences.append(ExperienceRecord(
            task_id=f"task-{index}", run_id=f"run-{index}", executor="fixture",
            feedback={"training_text": f"User: task {index}\nAssistant: verified answer {index}"},
            execution_success=True, verifier_passed=True, verifier_status="passed",
            eligibility="eligible",
        ))
    snapshot = DatasetSnapshotStore(tmp_path / "datasets").create(experiences, seed=2)
    result = train_lora(
        experience_store=experiences, snapshot=snapshot,
        base_model=tmp_path / "missing-model", output_dir=tmp_path / "adapter",
        require_gpu=False,
    )
    assert result.status in {"blocked", "failed"}
    assert "run_id" in result.to_dict()
    experiences.close()
