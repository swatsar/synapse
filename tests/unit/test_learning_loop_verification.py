"""Teacher output must be verified and deduplicated before training data write."""
from __future__ import annotations

import pytest

from synapse.core.models import ExecutionContext
from synapse.skills.builtins import learning_loop


def test_verify_pairs_drops_low_quality_and_duplicate_candidates():
    pairs = [
        {"prompt": "What is a list?", "response": "An ordered collection."},
        # Duplicate prompt in the same batch.
        {"prompt": "what is a list?", "response": "A mutable sequence."},
        {"prompt": "Hi", "response": "Hello"},
        {"prompt": "What is a list?", "response": "..."},
        {"prompt": "Explain Python", "response": "I can't help with that."},
        {"prompt": "Show traceback", "response": "Traceback (most recent call last): ..."},
        {"prompt": "What is a tuple?", "response": "An immutable sequence."},
        # Already learned in an earlier cycle.
        {"prompt": "What is a set?", "response": "An unordered collection."},
    ]
    from synapse.experience.store import training_fingerprint

    existing = {
        "text:"
        + training_fingerprint(
            "User: What is a set?\nAssistant: An unordered collection."
        )
    }

    accepted, report = learning_loop._verify_pairs(
        pairs, existing_identities=existing, min_pairs=2,
    )

    assert [pair["prompt"] for pair in accepted] == [
        "What is a list?",
        "What is a tuple?",
    ]
    assert report["passed"] is True
    assert report["received"] == 8
    assert report["accepted"] == 2
    assert report["dropped"]["duplicate_prompt"] == 1
    assert report["dropped"]["too_short"] == 1
    assert report["dropped"]["placeholder"] == 1
    assert report["dropped"]["refusal"] == 1
    assert report["dropped"]["error_output"] == 1
    assert report["dropped"]["already_learned"] == 1


def test_verify_pairs_fails_when_too_few_survive():
    accepted, report = learning_loop._verify_pairs(
        [
            {"prompt": "What is a list?", "response": "I cannot answer."},
            {"prompt": "OK", "response": "Sure"},
        ],
        min_pairs=2,
    )

    assert accepted == []
    assert report["passed"] is False


@pytest.mark.asyncio
async def test_learning_loop_blocks_and_writes_nothing_on_refusal_pairs(
    tmp_path, monkeypatch,
):
    async def fake_pairs(teacher, topic, language, count, workspace_root):
        return (
            [
                {"prompt": "Explain Python", "response": "I can't help with that."},
                {"prompt": "Explain ML", "response": "..."},
            ],
            {"teacher": "opencode/test-free", "kind": "opencode"},
        )

    def unexpected_training(**_kwargs):
        raise AssertionError("invalid pairs must never reach training")

    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(learning_loop, "_generate_pairs", fake_pairs)
    monkeypatch.setattr(learning_loop, "_default_model_id", lambda: "Qwen/test")
    monkeypatch.setattr("synapse.training.train_lora", unexpected_training)

    result = await learning_loop.execute_learning_loop(
        ExecutionContext(session_id="test", agent_id="test", trace_id="test"),
        topic="Python",
        teacher="opencode/test-free",
        pairs_per_cycle=2,
        max_cycles=1,
    )

    from synapse.experience import ExperienceStore

    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    try:
        assert store.count() == 0
    finally:
        store.close()
    assert result["success"] is False
    assert result["cycles"][0]["blocker"] == "pairs_failed_verification"
    assert result["cycles"][0]["verification"]["accepted"] == 0


@pytest.mark.asyncio
async def test_learning_loop_records_actual_teacher_provenance(
    tmp_path, monkeypatch,
):
    async def fake_pairs(teacher, topic, language, count, workspace_root):
        return (
            [
                {"prompt": "What is a list?", "response": "An ordered collection."},
                {"prompt": "What is a tuple?", "response": "An immutable sequence."},
            ],
            {"teacher": "opencode/test-free", "kind": "opencode"},
        )

    captured: dict[str, object] = {}

    class FakeResult:
        def to_dict(self):
            return {
                "status": "completed",
                "adapter_path": str(tmp_path / ".synapse" / "adapters" / "fake"),
                "promotion_status": "promoted",
                "final_loss": 0.5,
                "holdout_loss_before": 0.6,
                "holdout_loss_after": 0.55,
                "blockers": (),
                "error": None,
            }

    def fake_training(**kwargs):
        captured["metadata"] = kwargs["metadata"]
        return FakeResult()

    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(learning_loop, "_generate_pairs", fake_pairs)
    monkeypatch.setattr(learning_loop, "_default_model_id", lambda: "Qwen/test")
    monkeypatch.setattr(learning_loop, "_model_local_path", lambda model_id: str(tmp_path / "model"))
    monkeypatch.setattr("synapse.training.train_lora", fake_training)

    result = await learning_loop.execute_learning_loop(
        ExecutionContext(session_id="test", agent_id="test", trace_id="test"),
        topic="Python",
        teacher="opencode",
        pairs_per_cycle=2,
        max_cycles=1,
    )

    assert result["success"] is True
    assert captured["metadata"]["teacher"] == "opencode/test-free"
    assert captured["metadata"]["teacher_requested"] == "opencode"
    assert captured["metadata"]["teacher_kind"] == "opencode"

    from synapse.experience import ExperienceStore

    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    try:
        records = store.list_records(verified_only=True)
    finally:
        store.close()
    assert len(records) == 2
    assert all(record.model == "teacher:opencode/test-free" for record in records)
    assert all(record.provenance["teacher"] == "opencode/test-free" for record in records)
    assert all(
        record.provenance["pair_verification"]["accepted"] == 2
        for record in records
    )