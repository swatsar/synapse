"""Tests for promoted-adapter discovery and adapter-aware local inference.

Self-development only counts when the trained LoRA adapter actually changes
inference. These tests pin the selection rules: only promoted adapters of the
same base model are eligible, the newest promoted adapter wins, and the
process-wide provider cache is invalidated when a new adapter appears.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse.llm import local_model
from synapse.llm.local_model import (
    clear_local_provider_cache,
    discover_promoted_adapter,
    get_local_provider,
)


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
    base_model: str | Path | None = None,
) -> Path:
    adapter = model.parent.parent / "adapters" / name
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": str(base_model or model)}),
        encoding="utf-8",
    )
    (adapter / "training_manifest.json").write_text(
        json.dumps(
            {
                "base_model": str(base_model or model),
                "promotion_status": promotion_status,
            }
        ),
        encoding="utf-8",
    )
    return adapter


@pytest.fixture(autouse=True)
def _clean_adapter_env(monkeypatch):
    monkeypatch.delenv("SYNAPSE_ADAPTER_PATH", raising=False)
    monkeypatch.delenv("SYNAPSE_DISABLE_ADAPTERS", raising=False)
    clear_local_provider_cache()
    yield
    clear_local_provider_cache()


def test_promoted_adapter_is_discovered(tmp_path):
    model = _make_model(tmp_path)
    adapter = _make_adapter(model, "loop_01")

    assert discover_promoted_adapter(model) == adapter.resolve()


def test_rejected_adapter_is_ignored(tmp_path):
    model = _make_model(tmp_path)
    _make_adapter(model, "rejected", promotion_status="rejected")

    assert discover_promoted_adapter(model) is None


def test_adapter_for_another_base_model_is_ignored(tmp_path):
    model = _make_model(tmp_path)
    other = tmp_path / "other-model"
    other.mkdir()
    _make_adapter(model, "unrelated", base_model=other)

    assert discover_promoted_adapter(model) is None


def test_newest_promoted_adapter_wins(tmp_path):
    model = _make_model(tmp_path)
    older = _make_adapter(model, "older")
    newer = _make_adapter(model, "newer")
    # Filesystem mtimes can be equal at coarse resolution; make the order
    # explicit so this test is deterministic on every platform.
    older_manifest = older / "training_manifest.json"
    newer_manifest = newer / "training_manifest.json"
    older_manifest.touch()
    import os
    import time

    time.sleep(0.01)
    os.utime(newer, None)

    assert discover_promoted_adapter(model) == newer.resolve()


def test_explicit_adapter_path_wins(tmp_path, monkeypatch):
    model = _make_model(tmp_path)
    _make_adapter(model, "discovered")
    pinned = _make_adapter(model, "pinned")
    monkeypatch.setenv("SYNAPSE_ADAPTER_PATH", str(pinned))

    assert discover_promoted_adapter(model) == pinned.resolve()


def test_adapters_can_be_disabled(tmp_path, monkeypatch):
    model = _make_model(tmp_path)
    _make_adapter(model, "loop_01")
    monkeypatch.setenv("SYNAPSE_DISABLE_ADAPTERS", "1")

    assert discover_promoted_adapter(model) is None


def test_provider_cache_reloads_when_new_adapter_appears(tmp_path):
    model = _make_model(tmp_path)
    first = get_local_provider(model)
    assert first.adapter_path is None

    adapter = _make_adapter(model, "loop_01")
    second = get_local_provider(model)

    assert second is not first
    assert second.adapter_path == adapter.resolve()
    # The stale provider must not stay cached, otherwise every training run
    # keeps another full copy of the base weights alive.
    assert first not in local_model._PROVIDER_CACHE.values()


def test_adapter_status_reports_selection_and_real_load(tmp_path):
    from synapse.llm.local_model import adapter_status

    model = _make_model(tmp_path)
    adapter = _make_adapter(model, "loop_01")

    pending = adapter_status(model)
    assert pending["selected"] is True
    assert pending["applied"] is False
    assert pending["adapter_name"] == "loop_01"

    provider = get_local_provider(model)
    # Simulate a completed model load with the adapter applied.
    provider._adapter_applied = True
    loaded = adapter_status(model)
    assert loaded["loaded"] is True
    assert loaded["applied"] is True
    assert loaded["adapter_path"] == str(adapter.resolve())


def test_local_response_propagates_adapter_metadata(monkeypatch, tmp_path):
    """The executor must tell the user whether the trained adapter was used."""
    import asyncio
    from types import SimpleNamespace

    from synapse.skills.builtins import local_executor

    class FakeProvider:
        async def generate(self, prompt, **kwargs):
            return {
                "content": "answer",
                "provider": "local_transformers",
                "finish_reason": "stop",
                "truncated": False,
                "adapter_path": str(tmp_path / "adapters" / "loop_01"),
                "adapter_applied": True,
                "adapter_error": None,
                "usage": {},
            }

    monkeypatch.setattr(
        "synapse.llm.local_model.get_local_provider", lambda *a, **k: FakeProvider()
    )
    manifest = SimpleNamespace(
        model_id="local/test", local_path=str(tmp_path / "model")
    )
    result = asyncio.run(local_executor._local_response(manifest, "hi", 128))
    assert result["adapter_applied"] is True
    assert result["adapter_path"].endswith("loop_01")
    assert result["adapter_error"] is None


def test_chat_template_receives_synapse_identity():
    """A generic checkpoint must be told that it is Synapse, not a stranger."""

    class FakeTokenizer:
        chat_template = "fake"

        def __init__(self):
            self.messages = []

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            self.messages = messages
            return "\n".join(f"{item['role']}: {item['content']}" for item in messages)

    tokenizer = FakeTokenizer()
    text = local_model.LocalTransformersProvider._format_prompt(tokenizer, "Кто ты?")

    assert tokenizer.messages[0]["role"] == "system"
    assert "Synapse" in tokenizer.messages[0]["content"]
    assert tokenizer.messages[-1] == {"role": "user", "content": "Кто ты?"}
    assert "system:" in text


def test_chat_template_falls_back_when_system_role_is_unsupported():
    class NoSystemTokenizer:
        chat_template = "fake"

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            if any(item["role"] == "system" for item in messages):
                raise ValueError("system role unsupported")
            return messages[0]["content"]

    text = local_model.LocalTransformersProvider._format_prompt(
        NoSystemTokenizer(), "Кто ты?"
    )
    assert text == "Кто ты?"


def test_chat_template_without_template_uses_raw_prompt():
    class PlainTokenizer:
        chat_template = None

    text = local_model.LocalTransformersProvider._format_prompt(
        PlainTokenizer(), "raw prompt"
    )
    assert text == "raw prompt"
