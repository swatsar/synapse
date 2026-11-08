import pytest

from synapse.experience import ExperienceRecord, ExperienceStore


def test_record_hash_is_deterministic_and_verified_requires_independent_verifier():
    record = ExperienceRecord(
        task_id="task-1",
        run_id="run-1",
        objective="Read a file",
        executor="builtin/read_file",
        execution_success=True,
        verifier_passed=None,
        verifier_status="inconclusive",
        eligibility="ineligible",
    )
    assert len(record.record_hash) == 64
    assert record.verified_for_training is False

    verified = ExperienceRecord(
        task_id="task-1",
        run_id="run-1",
        objective="Read a file",
        executor="builtin/read_file",
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    )
    assert verified.verified_for_training is True


def test_store_verified_only_boundary_and_duplicate_hash(tmp_path):
    store = ExperienceStore(tmp_path / "experience.sqlite3")
    observed = ExperienceRecord(
        task_id="task-observed",
        run_id="run-observed",
        executor="fixture",
        execution_success=True,
        verifier_passed=None,
        verifier_status="inconclusive",
    )
    verified = ExperienceRecord(
        task_id="task-verified",
        run_id="run-verified",
        executor="fixture",
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    )
    store.append(observed)
    store.append(verified)
    assert store.count() == 2
    assert [r.task_id for r in store.list_records(verified_only=True)] == ["task-verified"]
    with pytest.raises(Exception):
        store.append(verified)
    store.close()
