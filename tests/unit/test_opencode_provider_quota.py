"""OpenCode runtime notices must never surface as assistant chat content."""
from __future__ import annotations

import asyncio
import json
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
    assert opencode_bridge.is_opencode_quota_exhausted() is True


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