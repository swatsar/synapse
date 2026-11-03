"""
Unit tests for SlashCommandEngine (anthropics/claude-code integration).
"""

import pytest
from synapse.interfaces.slash_engine import SlashCommandEngine, SlashCommandDef, PROTOCOL_VERSION


@pytest.fixture
def engine():
    return SlashCommandEngine()


def test_protocol_version(engine):
    cmds = engine.list_commands()
    assert len(cmds) >= 5
    for c in cmds:
        assert c.protocol_version == PROTOCOL_VERSION


@pytest.mark.asyncio
async def test_help_command(engine):
    res = await engine.execute("/help")
    assert res.success is True
    assert "available_commands" in res.output
    names = [c["command"] for c in res.output["available_commands"]]
    assert "/help" in names
    assert "/audit" in names
    assert "/memory" in names
    assert "/bench" in names
    assert "/model" in names


@pytest.mark.asyncio
async def test_unknown_command(engine):
    res = await engine.execute("/unknown_cmd")
    assert res.success is False
    assert "Unknown command: /unknown_cmd" in res.output


@pytest.mark.asyncio
async def test_model_command(engine):
    res = await engine.execute('/model "Review python security AST"')
    assert res.success is True
    assert "model" in res.output
    assert res.output["detected_domain"] in {"coding", "security"}


@pytest.mark.asyncio
async def test_memory_command(engine):
    # Add note
    res_add = await engine.execute('/memory add "Key Convention" "Always run basetemp"')
    assert res_add.success is True
    assert "created" in res_add.output

    # Search note
    res_search = await engine.execute('/memory search "basetemp"')
    assert res_search.success is True
    assert len(res_search.output["results"]) >= 1


@pytest.mark.asyncio
async def test_skills_command_forwards_parameters(engine):
    res = await engine.execute('/skills run model_route \'{"task":"Write Python"}\'')
    assert res.success is True
    assert res.output["result"]["decision"]["detected_domain"] == "coding"


@pytest.mark.asyncio
async def test_skills_command_accepts_unquoted_json_with_spaces(engine):
    res = await engine.execute('/skills run model_route {"task": "Write Python"}')
    assert res.success is True
    assert res.output["result"]["decision"]["detected_domain"] == "coding"


@pytest.mark.asyncio
async def test_skills_command_reports_invalid_json(engine):
    res = await engine.execute('/skills run model_route {"task":}')
    assert res.success is True
    assert "Invalid skill parameters JSON" in res.output["error"]


@pytest.mark.asyncio
async def test_unclosed_quote_is_command_error(engine):
    res = await engine.execute('/memory search "unclosed')
    assert res.success is False
    assert "Invalid command syntax" in res.output


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/ast ../outside.py", "/patch ../outside.py"])
async def test_file_commands_reject_workspace_escape(engine, monkeypatch, tmp_path, command):
    from synapse.integrations.codex_engine import CodexEngine

    monkeypatch.setattr(
        "synapse.integrations.codex_engine.get_codex_engine",
        lambda: CodexEngine(tmp_path / "workspace"),
    )
    res = await engine.execute(command)
    assert res.success is True
    assert res.output == {"error": "File path escapes workspace root."}


@pytest.mark.asyncio
async def test_bench_command(engine):
    res = await engine.execute("/bench custom_run")
    assert res.success is True
    assert "suite_id" in res.output
    assert res.output["grade"] in {"A+", "A", "B", "C", "F"}
