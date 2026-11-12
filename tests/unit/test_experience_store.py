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


def test_human_approval_promotes_candidate_answer(tmp_path):
    store = ExperienceStore(tmp_path / "experience.sqlite3")
    record = ExperienceRecord(
        task_id="task-human",
        run_id="run-human",
        objective="What is 2 + 2?",
        executor="orchestrator.handle",
        provider="local_transformers",
        model="local/qwen",
        execution_success=True,
        verifier_passed=None,
        verifier_status="inconclusive",
        eligibility="ineligible",
        feedback={
            "model_backed": True,
            "candidate_training_text": (
                "User: What is 2 + 2?\nAssistant: The answer is 4."
            ),
        },
    )
    store.append(record)

    updated = store.apply_human_verification(
        "task-human", passed=True, note="correct",
    )

    assert updated is not None
    assert updated.verified_for_training is True
    assert updated.verifier_status == "passed"
    assert updated.eligibility == "eligible"
    assert updated.feedback["training_text"].endswith("The answer is 4.")
    assert updated.feedback["human_feedback"] == {"passed": True, "note": "correct"}
    assert updated.record_hash != record.record_hash
    assert [item.task_id for item in store.list_records(verified_only=True)] == ["task-human"]
    store.close()


def test_human_rejection_removes_training_text(tmp_path):
    store = ExperienceStore(tmp_path / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="task-rejected",
        run_id="run-rejected",
        objective="What is 2 + 2?",
        executor="orchestrator.handle",
        execution_success=True,
        verifier_passed=None,
        verifier_status="inconclusive",
        eligibility="ineligible",
        feedback={
            "model_backed": True,
            "candidate_training_text": "User: q\nAssistant: wrong",
        },
    ))

    updated = store.apply_human_verification(
        "task-rejected", passed=False, note="wrong answer",
    )

    assert updated is not None
    assert updated.verified_for_training is False
    assert updated.verifier_passed is False
    assert "training_text" not in updated.feedback
    assert store.list_records(verified_only=True) == []
    assert store.latest_for_task("missing-task") is None
    store.close()
