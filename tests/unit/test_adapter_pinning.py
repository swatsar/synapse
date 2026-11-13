"""Explicit adapter pinning and rollback.

Before this feature inference always picked the newest promoted adapter by
mtime. A regression could not be rolled back without deleting files, which
makes autonomous self-training unsafe to leave running.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from synapse.llm import local_model
from synapse.llm.local_model import clear_local_provider_cache, discover_promoted_adapter
from synapse.training.adapters import list_adapters, pin_adapter, unpin_adapter


def _make_model(tmp_path: Path) -> Path:
    model = tmp_path / ".synapse" / "models" / "base-model"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    return model


def _make_adapter(
    model: Path,
    name: str,
    *,
    promotion_status: str = "promoted",
    holdout_after: float = 1.0,
    topic: str | None = None,
) -> Path:
    adapter = model.parent.parent / "adapters" / name
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": str(model)}), encoding="utf-8"
    )
    manifest = {
        "base_model": str(model),
        "promotion_status": promotion_status,
        "holdout_loss_before": 2.0,
        "holdout_loss_after": holdout_after,
        "steps": 3,
        "records": 10,
    }
    if topic:
        manifest["topic"] = topic
    (adapter / "training_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return adapter


def _age(path: Path, seconds: float) -> None:
    stamp = path.stat().st_mtime - seconds
    os.utime(path, (stamp, stamp))


@pytest.fixture(autouse=True)
def _clean_adapter_env(monkeypatch):
    monkeypatch.delenv("SYNAPSE_ADAPTER_PATH", raising=False)
    monkeypatch.delenv("SYNAPSE_DISABLE_ADAPTERS", raising=False)
    clear_local_provider_cache()
    yield
    clear_local_provider_cache()


def test_pin_wins_over_newer_adapter(tmp_path):
    model = _make_model(tmp_path)
    older = _make_adapter(model, "older")
    newer = _make_adapter(model, "newer")
    _age(older, 120)

    assert discover_promoted_adapter(model) == newer.resolve()

    pin_adapter(tmp_path, "older")
    assert discover_promoted_adapter(model) == older.resolve()

    unpin_adapter(tmp_path)
    assert discover_promoted_adapter(model) == newer.resolve()


def test_invalid_pin_falls_back_to_newest_promoted(tmp_path):
    model = _make_model(tmp_path)
    older = _make_adapter(model, "older")
    newer = _make_adapter(model, "newer")
    _age(older, 120)
    pin_adapter(tmp_path, "older")

    # An adapter that is no longer promoted must not keep owning inference.
    (older / "training_manifest.json").write_text(
        json.dumps(
            {"base_model": str(model), "promotion_status": "rejected"}
        ),
        encoding="utf-8",
    )

    assert discover_promoted_adapter(model) == newer.resolve()


def test_deleted_pinned_adapter_falls_back(tmp_path):
    model = _make_model(tmp_path)
    _make_adapter(model, "older")
    newer = _make_adapter(model, "newer")
    pin_adapter(tmp_path, "older")
    for child in (model.parent.parent / "adapters" / "older").iterdir():
        child.unlink()
    (model.parent.parent / "adapters" / "older").rmdir()

    assert discover_promoted_adapter(model) == newer.resolve()


def test_only_promoted_adapters_can_be_pinned(tmp_path):
    model = _make_model(tmp_path)
    _make_adapter(model, "rejected", promotion_status="rejected")

    with pytest.raises(ValueError):
        pin_adapter(tmp_path, "rejected")
    with pytest.raises(FileNotFoundError):
        pin_adapter(tmp_path, "missing")
    with pytest.raises(ValueError):
        pin_adapter(tmp_path, "../escape")


def test_history_reports_selection_and_pin(tmp_path):
    model = _make_model(tmp_path)
    older = _make_adapter(model, "older", topic="Python memory", holdout_after=1.5)
    newer = _make_adapter(model, "newer", holdout_after=1.2)
    _age(older, 120)

    rows = {row["name"]: row for row in list_adapters(tmp_path, model_path=model)}
    assert rows["newer"]["selected"] is True
    assert rows["older"]["selected"] is False
    assert rows["older"]["topic"] == "Python memory"
    assert rows["older"]["records"] == 10

    pin_adapter(tmp_path, "older")
    rows = {row["name"]: row for row in list_adapters(tmp_path, model_path=model)}
    assert rows["older"]["pinned"] is True
    assert rows["older"]["selected"] is True
    assert rows["newer"]["selected"] is False
    assert rows["older"]["path"] == str(older.resolve())


def test_explicit_env_still_overrides_pin(tmp_path, monkeypatch):
    model = _make_model(tmp_path)
    _make_adapter(model, "older")
    newer = _make_adapter(model, "newer")
    pin_adapter(tmp_path, "older")
    monkeypatch.setenv("SYNAPSE_ADAPTER_PATH", str(newer))

    assert discover_promoted_adapter(model) == newer.resolve()
    assert local_model.discover_promoted_adapter(model) == newer.resolve()
