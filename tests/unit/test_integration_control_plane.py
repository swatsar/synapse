from __future__ import annotations

import pytest

from synapse.harnesses import CodexHarness, HarnessRequest
from synapse.integrations.control_plane import IntegrationControlPlane


def test_write_harness_requires_confirmation_and_scope(tmp_path):
    harness = CodexHarness(enabled=True, write_enabled=True)
    request = HarnessRequest(
        "task", "run", "inspect", metadata={"workspace_root": str(tmp_path)}
    )
    argv = harness.build_argv("codex", request, tmp_path)
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"


@pytest.mark.asyncio
async def test_write_harness_rejects_missing_confirmation(tmp_path):
    harness = CodexHarness(enabled=True, write_enabled=True)
    result = await harness.execute(HarnessRequest(
        "task", "run", "inspect", metadata={"workspace_root": str(tmp_path)}
    ))
    assert result.success is False
    assert "write_confirmation" in result.error


@pytest.mark.asyncio
async def test_write_harness_accepts_nested_workspace_scope_but_reports_missing_cli(tmp_path):
    workspace = tmp_path / "nested"
    workspace.mkdir()
    harness = CodexHarness(enabled=True, executable="definitely-not-installed", write_enabled=True)
    result = await harness.execute(HarnessRequest(
        "task", "run", "inspect", metadata={
            "workspace_root": str(workspace),
            "workspace_scope": str(tmp_path),
            "write_confirmation": True,
        }
    ))
    assert result.success is False
    assert "executable not found" in result.error


def test_control_plane_rejects_secret_bearing_mcp_declaration(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    control_plane = IntegrationControlPlane()
    with pytest.raises(ValueError, match="secret-bearing"):
        control_plane.upsert_mcp({
            "id": "secret-server",
            "transport": "streamable_http",
            "url": "https://example.test/mcp?api_key=do-not-store",
        })
