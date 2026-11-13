import pytest

from synapse.experience import DatasetSnapshotStore, ExperienceRecord, ExperienceStore


def _verified(task_id: str) -> ExperienceRecord:
    return ExperienceRecord(
        task_id=task_id,
        run_id=f"run-{task_id}",
        executor="fixture",
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    )


def test_snapshot_requires_verified_records_and_is_deterministically_split(tmp_path):
    experiences = ExperienceStore(tmp_path / "experience.sqlite3")
    experiences.append(ExperienceRecord(task_id="unverified", execution_success=True))
    with pytest.raises(ValueError, match="No verified experience"):
        DatasetSnapshotStore(tmp_path / "datasets").create(experiences)

    for index in range(10):
        experiences.append(_verified(f"task-{index}"))
    snapshots = DatasetSnapshotStore(tmp_path / "datasets")
    first = snapshots.create(experiences, seed=42)
    second = snapshots.create(experiences, seed=42)
    assert first.manifest_hash == second.manifest_hash
    assert set(first.train_ids) | set(first.dev_ids) | set(first.holdout_ids) == set(first.source_record_ids)
    assert not set(first.train_ids) & set(first.dev_ids)
    assert not set(first.train_ids) & set(first.holdout_ids)
    assert not set(first.dev_ids) & set(first.holdout_ids)
    assert snapshots.load(first.snapshot_id).manifest_hash == first.manifest_hash
    experiences.close()


def test_snapshot_deduplicates_identical_training_texts(tmp_path):
    experiences = ExperienceStore(tmp_path / "experience.sqlite3")
    text = "User: What is a list?\nAssistant: An ordered collection."
    for index in range(4):
        experiences.append(ExperienceRecord(
            task_id=f"task-dup-{index}",
            run_id=f"run-dup-{index}",
            executor="fixture",
            execution_success=True,
            verifier_passed=True,
            verifier_status="passed",
            eligibility="eligible",
            feedback={"training_text": text},
        ))
    snapshot = DatasetSnapshotStore(tmp_path / "datasets").create(
        experiences, seed=7,
    )
    assert len(snapshot.source_record_ids) == 1
    assert snapshot.metadata["source_record_count"] == 4
    assert snapshot.metadata["verified_record_count"] == 1
    assert snapshot.metadata["duplicate_records_dropped"] == 3
    experiences.close()
