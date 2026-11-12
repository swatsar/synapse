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


def test_autonomous_training_defaults_to_cpu_without_gpu_requirement(monkeypatch):
    """A shared GPU must not turn a non-GPU training run into a CUDA OOM."""
    from synapse.training.trainer import _select_device

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

    class FakeTorch:
        cuda = FakeCuda()

    monkeypatch.delenv("SYNAPSE_TRAIN_DEVICE", raising=False)
    assert _select_device(FakeTorch(), require_gpu=False) == "cpu"
    assert _select_device(FakeTorch(), require_gpu=True) == "cuda"

    monkeypatch.setenv("SYNAPSE_TRAIN_DEVICE", "cuda")
    assert _select_device(FakeTorch(), require_gpu=False) == "cuda"

    class NoCuda:
        class cuda:
            @staticmethod
            def is_available():
                return False

    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        _select_device(NoCuda(), require_gpu=False)


def test_masked_labels_ignore_padding_positions():
    """Causal-LM loss must not be computed over padding tokens."""
    torch = pytest.importorskip("torch")
    from synapse.training.trainer import _masked_labels

    input_ids = torch.tensor([[5, 6, 0, 0], [7, 0, 0, 0]])
    attention_mask = torch.tensor([[1, 1, 0, 0], [1, 0, 0, 0]])
    labels = _masked_labels(input_ids, attention_mask)
    assert labels.tolist() == [[5, 6, -100, -100], [7, -100, -100, -100]]


def test_text_batches_split_large_datasets_into_bounded_chunks():
    """A full dataset must never become one huge forward-pass batch."""
    from synapse.training.trainer import _text_batches

    texts = [f"text {index}" for index in range(10)]
    batches = _text_batches(texts, 4)
    assert [len(batch) for batch in batches] == [4, 4, 2]
    assert [item for batch in batches for item in batch] == texts
    # A nonsensical size still produces forward progress.
    assert _text_batches(texts, 0) == [[text] for text in texts]


def test_loss_on_records_batches_holdout_forward_passes():
    """Holdout loss used to tokenize every record at once and OOM the CPU."""
    torch = pytest.importorskip("torch")
    from types import SimpleNamespace

    from synapse.training.trainer import _loss_on_records

    observed: list[int] = []

    class FakeTokenizer:
        def __call__(self, texts, **kwargs):
            observed.append(len(texts))
            count = len(texts)
            return {
                "input_ids": torch.ones((count, 4), dtype=torch.long),
                "attention_mask": torch.ones((count, 4), dtype=torch.long),
            }

    class FakeModel:
        def eval(self):
            return self

        def __call__(self, input_ids, attention_mask, labels):
            assert input_ids.shape[0] <= 3
            return SimpleNamespace(loss=torch.tensor(2.0))

    records = [
        SimpleNamespace(
            objective=f"task {index}",
            feedback={"training_text": f"text {index}"},
        )
        for index in range(10)
    ]
    loss = _loss_on_records(
        FakeModel(), FakeTokenizer(), records, "cpu", 64, batch_size=3,
    )
    assert loss == pytest.approx(2.0)
    assert observed == [3, 3, 3, 1]


def test_behavior_probes_extract_deterministic_output_criteria():
    from types import SimpleNamespace

    from synapse.training.trainer import _behavior_probes

    records = [
        SimpleNamespace(
            objective="Say the word banana",
            feedback={"verification": {"checks": [
                {"criterion": "output_contains:banana", "passed": True},
                {"criterion": "file_exists:out.txt", "passed": True},
            ]}},
        ),
        SimpleNamespace(objective="", feedback={"verification": {"checks": [
            {"criterion": "output_contains:x", "passed": True},
        ]}}),
        SimpleNamespace(objective="No checks", feedback={}),
    ]
    probes = _behavior_probes(records)
    assert probes == [
        {"objective": "Say the word banana", "criteria": ["output_contains:banana"]},
    ]


def test_fixed_behavior_probes_always_guard_identity_and_instruction_following():
    """A fresh store has no record probes; the gate must still check behaviour."""
    from synapse.training.trainer import _fixed_behavior_probes

    probes = _fixed_behavior_probes()
    assert len(probes) >= 3
    assert any("Synapse" in probe["objective"] for probe in probes)
    assert all(
        criterion.startswith("output_contains:")
        for probe in probes
        for criterion in probe["criteria"]
    )


def test_promotion_requires_holdout_improvement_and_no_behavioural_regression():
    from synapse.training.trainer import _criterion_passes, _promotion_decision

    assert _criterion_passes("output_contains:banana", "a banana")
    assert not _criterion_passes("output_contains:banana", "apple")
    assert _criterion_passes("output_not_contains:error", "ok")

    promoted, gate, status = _promotion_decision(
        holdout_loss_before=1.0, holdout_loss_after=0.9,
        behavioral_probes=0, behavioral_before=None, behavioral_after=None,
    )
    assert promoted is True
    assert gate == "holdout_loss_after_lt_before"
    assert status == "promoted"

    promoted, gate, status = _promotion_decision(
        holdout_loss_before=1.0, holdout_loss_after=0.9,
        behavioral_probes=3, behavioral_before=2, behavioral_after=2,
    )
    assert promoted is True
    assert gate == "holdout_loss_and_no_behavioral_regression"
    assert status == "promoted"

    promoted, gate, status = _promotion_decision(
        holdout_loss_before=1.0, holdout_loss_after=0.9,
        behavioral_probes=3, behavioral_before=2, behavioral_after=1,
    )
    assert promoted is False
    assert gate == "holdout_loss_and_no_behavioral_regression"
    assert status == "blocked_behavioral_regression"

    promoted, _, status = _promotion_decision(
        holdout_loss_before=1.0, holdout_loss_after=1.0,
        behavioral_probes=3, behavioral_before=1, behavioral_after=3,
    )
    assert promoted is False
    assert status == "blocked_no_holdout_improvement"


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
