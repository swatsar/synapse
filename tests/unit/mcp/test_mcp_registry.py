"""Unit tests for MCP Control Layer registry."""
import pytest
from synapse.mcp import McpRegistry, McpServerRecord, McpTransport


def test_register_and_get_server():
    reg = McpRegistry()
    rec = McpServerRecord(
        id="test-server",
        transport=McpTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-test"],
        workspace_id="ws-1",
    )
    reg.register(rec)
    assert reg.get("test-server") is rec
    assert reg.get("missing") is None


def test_list_filters_by_workspace():
    reg = McpRegistry()
    reg.register(McpServerRecord(id="a", transport=McpTransport.STDIO, command="x", workspace_id="ws-1"))
    reg.register(McpServerRecord(id="b", transport=McpTransport.STDIO, command="y", workspace_id="ws-2"))
    reg.register(McpServerRecord(id="c", transport=McpTransport.STDIO, command="z", workspace_id=None))

    ws1 = reg.list(workspace_id="ws-1")
    assert {r.id for r in ws1} == {"a", "c"}

    all_servers = reg.list()
    assert len(all_servers) == 3


def test_unregister_removes_server():
    reg = McpRegistry()
    reg.register(McpServerRecord(id="x", transport=McpTransport.STDIO, command="cmd"))
    assert reg.unregister("x") is True
    assert reg.get("x") is None
    assert reg.unregister("x") is False


def test_record_is_frozen():
    rec = McpServerRecord(id="f", transport=McpTransport.STREAMABLE_HTTP, url="https://mcp.test")
    with pytest.raises(AttributeError):
        rec.id = "changed"
