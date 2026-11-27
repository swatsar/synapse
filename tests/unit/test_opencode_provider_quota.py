"""OpenCode runtime notices must never surface as assistant chat content."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.integrations import opencode_bridge
from synapse.llm import opencode_provider
from synapse.llm.opencode_provider import OpenCodeCLIProvider, OpenCodeQuotaExceeded


def _events(*payloads: dict) -> str:
    return "\n".join(json.dumps(item) for item in payloads)


def _patch_runner(monkeypatch, stdout: str) -> None:
    monkeypatch.setattr(
        opencode_provider, "find_opencode_cli", lambda: "opencode"
    )
    monkeypatch.setattr(
        opencode_provider.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=stdout, stderr=""),
    )


@pytest.fixture(autouse=True)
def _isolated_health(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_OPENCODE_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setenv("SYNAPSE_OPENCODE_QUOTA_COOLDOWN", "120")
    opencode_bridge.reset_opencode_health()
    yield
    opencode_bridge.reset_opencode_health()


def test_quota_notice_text_is_a_failure_not_an_answer(monkeypatch):
    """Regression: the subscribe line appeared in the chat as assistant text."""
    notice = (
        "You've hit your free usage limit. "
        "Subscribe to OpenCode Go to keep going: https://opencode.ai/go"
    )
    _patch_runner(monkeypatch, _events({"type": "text", "text": notice}))

    with pytest.raises(OpenCodeQuotaExceeded) as excinfo:
        asyncio.run(OpenCodeCLIProvider("opencode/free").generate("hello"))

    assert "free usage limit" in str(excinfo.value).lower()
    assert excinfo.value.retry_after_seconds > 0
    assert opencode_bridge.is_opencode_quota_exhausted("opencode/free") is True


def test_error_event_wins_over_streamed_text(monkeypatch):
    """Partial text must not hide a failed run."""
    stdout = _events(
        {"type": "text", "text": "Here is a partial answer"},
        {"type": "error", "error": {"message": "Free usage limit reached"}},
    )
    _patch_runner(monkeypatch, stdout)

    with pytest.raises(OpenCodeQuotaExceeded):
        asyncio.run(OpenCodeCLIProvider("opencode/free").generate("hello"))


def test_quota_line_is_stripped_from_a_real_answer(monkeypatch):
    answer = (
        "A list is an ordered mutable sequence.\n"
        "Subscribe to OpenCode Go to keep going: https://opencode.ai/go"
    )
    _patch_runner(monkeypatch, _events({"type": "text", "text": answer}))

    result = asyncio.run(OpenCodeCLIProvider("opencode/free").generate("hello"))

    assert result["content"] == "A list is an ordered mutable sequence."
    assert "opencode.ai/go" not in result["content"]

def test_local_profile_only_runs_open_code_for_a_selected_model(monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOCAL_ONLY", "1")
    monkeypatch.setenv("SYNAPSE_ALLOW_SELECTED_OPENCODE", "1")
    monkeypatch.setenv("SYNAPSE_SECRET_KEY", "synapse-private-test-value")
    monkeypatch.setenv("SYNAPSE_API_KEY", "synapse-access-test-value")
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", json.dumps({
        "agents": {"build": {"description": "Override the stock agent"}},
    }))
    monkeypatch.setattr(opencode_provider, "find_opencode_cli", lambda: "opencode")
    monkeypatch.setattr(opencode_provider, "list_opencode_models", lambda: ["opencode/test-free"])
    calls = []

    def run(argv, *, env, cwd, **kwargs):
        calls.append(argv)
        assert "SYNAPSE_SECRET_KEY" not in env and "SYNAPSE_API_KEY" not in env
        assert Path(cwd).name.startswith("synapse-opencode-")
        config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert argv[argv.index("--agent") + 1] == "build"
        assert "build" not in config.get("agents", {})
        assert {"action": "tool.use", "resource": "*", "effect": "deny"} in config["experimental"]["policies"]
        return SimpleNamespace(stdout=_events({"type": "text", "text": "OK"}), stderr="")

    monkeypatch.setattr(opencode_provider.subprocess, "run", run)
    provider = OpenCodeCLIProvider("opencode/test-free")
    with pytest.raises(RuntimeError, match="explicitly selected"):
        asyncio.run(provider.generate("local task"))
    assert not calls
    with pytest.raises(RuntimeError, match="absent from the catalog"):
        asyncio.run(OpenCodeCLIProvider("opencode/unknown").generate("not sent", selected_by_user=True))
    assert not calls
    result = asyncio.run(provider.generate("--user text", selected_by_user=True))
    assert result["content"] == "OK"
    assert calls[0][-2:] == ["--", "--user text"]


def test_one_models_quota_does_not_disable_another_model():
    first = "opencode/beam-free"
    second = "opencode/seaglass-alpha-free"
    opencode_bridge.record_opencode_failure("Free usage limit reached", model_id=first)
    assert opencode_bridge.quota_status(first)["exhausted"] is True
    assert opencode_bridge.quota_status(second)["exhausted"] is False
    assert opencode_bridge.quota_status()["exhausted"] is False
    opencode_bridge.record_opencode_success(model_id=second)
    assert opencode_bridge.quota_status(first)["exhausted"] is True


def test_old_agent_quota_does_not_block_the_builtin_agent():
    model = "opencode/seaglass-alpha-free"
    opencode_bridge._health_path().write_text(json.dumps({
        "profile": opencode_bridge._profile_id(),
        "model_quotas": {model: [time.time() + 120, "Free usage limit reached"]},
    }), encoding="utf-8")

    opencode_bridge._load_health()

    assert not opencode_bridge.is_opencode_quota_exhausted(model)


def test_router_and_open_code_status_agree_on_model_cooldown(monkeypatch):
    from synapse.llm.omnirouter import OmniRouter

    limited = "opencode/beam-free"
    ready = "opencode/seaglass-alpha-free"
    monkeypatch.setattr(opencode_bridge, "find_opencode_cli", lambda: Path("opencode"))
    monkeypatch.setattr(opencode_bridge, "list_opencode_models", lambda: [limited, ready])
    opencode_bridge.record_opencode_failure("Free usage limit reached", model_id=limited)

    status = opencode_bridge.opencode_status()
    assert status["status"] == "ready"
    assert set(status["model_quotas"]) == {limited}
    assert status["preferred_model"] == ready

    router = OmniRouter()
    asyncio.run(router.refresh_providers())
    catalog = {item["id"]: item for item in router.get_catalog()}
    assert catalog[limited]["unavailable_reason"] == "quota_exhausted"
    assert catalog[ready]["available"] is True
    assert not router._candidate_ready("opencode", limited, {})
    assert router._candidate_ready("opencode", ready, {})
