import json
import sys

import pytest

from synapse.harnesses import (
    ClaudeCodeHarness,
    CodexHarness,
    ExternalCliHarness,
    HarnessRequest,
    parse_jsonl,
)


@pytest.mark.asyncio
async def test_harness_is_execution_adapter_not_orchestrator():
    result = await CodexHarness().execute(HarnessRequest("t", "r", "implement"))
    assert result.success is False
    assert "not configured" in result.error


def test_jsonl_parser_preserves_unknown_events_and_final_text():
    events, output = parse_jsonl(
        '{"type":"thread.started","id":"x"}\n'
        '{"type":"agent_message","message":{"content":"done"}}\n'
        'not-json\n'
    )
    assert len(events) == 3
    assert output == "done"
    assert events[-1]["type"] == "unparsed_line"


def test_external_cli_argv_is_scoped_and_non_bypass():
    request = HarnessRequest("t", "r", "inspect", workspace_id="C:/workspace")
    codex = CodexHarness(enabled=True)
    codex_argv = codex.build_argv("codex", request, __import__("pathlib").Path("C:/workspace"))
    assert "--sandbox" in codex_argv
    assert "read-only" in codex_argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in codex_argv

    claude = ClaudeCodeHarness(enabled=True)
    claude_argv = claude.build_argv("claude", request, __import__("pathlib").Path("C:/workspace"))
    assert "--permission-mode" in claude_argv
    assert "dontAsk" in claude_argv
    assert "--dangerously-skip-permissions" not in claude_argv


class FixtureCliHarness(ExternalCliHarness):
    name = "fixture"
    command = sys.executable

    def build_argv(self, executable, request, workspace):
        payload = json.dumps({"type": "result", "result": request.prompt})
        return [executable, "-c", f"print({payload!r})"]


@pytest.mark.asyncio
async def test_fixture_cli_produces_real_receipt(tmp_path):
    harness = FixtureCliHarness(enabled=True, timeout_seconds=5)
    result = await harness.execute(
        HarnessRequest("t", "r", "fixture-output", metadata={"workspace_root": str(tmp_path)})
    )
    assert result.success is True
    assert result.output == "fixture-output"
    assert result.receipt["status"] == "completed"
    assert result.receipt["returncode"] == 0
