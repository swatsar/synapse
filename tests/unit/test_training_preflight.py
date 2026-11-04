from synapse.experience import DatasetSnapshot
from synapse.training import check_training_preflight


def test_training_preflight_blocks_without_runtime_and_snapshot():
    result = check_training_preflight(snapshot=None, base_model=None)
    assert result.ready is False
    assert result.status == "blocked"
    assert "verified_dataset_snapshot_required" in result.blockers
    assert "frozen_open_weight_base_model_required" in result.blockers
    if result.evidence["missing_python_packages"]:
        assert any(item.startswith("missing_training_dependencies:") for item in result.blockers)


def test_training_preflight_requires_holdout():
    snapshot = DatasetSnapshot(
        snapshot_id="ds-test",
        schema_version="1.0",
        source_record_ids=("a",),
        train_ids=("a",),
        dev_ids=(),
        holdout_ids=(),
        manifest_hash="hash",
        created_at="now",
    )
    result = check_training_preflight(snapshot=snapshot, base_model="local-model", require_gpu=False)
    assert result.ready is False
    assert "non_empty_holdout_required" in result.blockers
