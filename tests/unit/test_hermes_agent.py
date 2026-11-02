"""
Unit tests for Hermes Agent structured scratchpad and error recovery (NousResearch/hermes-agent integration).
"""

import pytest
from synapse.agents.hermes_agent import HermesAgent, HermesParser, HermesTurn, PROTOCOL_VERSION


def test_protocol_version():
    turn = HermesTurn(thought="Planning test")
    assert turn.protocol_version == PROTOCOL_VERSION


def test_scratchpad_parser():
    raw = """
    <thought>
    I need to inspect the current repository structure.
    </thought>
    <action>
    {
      "tool": "list_directory",
      "params": {"path": "."}
    }
    </action>
    <reflection>
    Ensure we do not traverse into excluded dirs like .venv.
    </reflection>
    """
    turn = HermesParser.parse(raw)
    assert "inspect the current repository" in turn.thought
    assert turn.action is not None
    assert turn.action["tool"] == "list_directory"
    assert turn.action["params"]["path"] == "."
    assert "Ensure we do not traverse" in turn.reflection
    assert turn.is_terminal is False


def test_format_scratchpad():
    formatted = HermesParser.format_scratchpad(
        thought="Verifying router catalog",
        action={"tool": "get_catalog"},
        reflection="Catalog retrieved",
    )
    assert "<thought>" in formatted
    assert "<action>" in formatted
    assert "<reflection>" in formatted


@pytest.mark.asyncio
async def test_hermes_agent_execution_and_recovery():
    call_counts = {"count": 0}

    async def mock_executor(tool: str, params: dict):
        call_counts["count"] += 1
        if call_counts["count"] == 1:
            raise ValueError("File locked or permission denied on first try")
        return "Success on attempt 2"

    agent = HermesAgent(tool_executor=mock_executor, max_retries=2)
    scratchpad = """
    <thought>Reading file</thought>
    <action>{"tool": "read_file", "params": {"file": "test.txt"}}</action>
    """
    turn = await agent.execute_step_with_recovery(scratchpad)
    assert call_counts["count"] == 2
    assert turn.observation == "Success on attempt 2"
    assert "Tool 'read_file' executed successfully." in turn.reflection
