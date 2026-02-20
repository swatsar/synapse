"""Tests for Tool Schema."""

import pytest

import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.tool_schema import (
    ToolSchema,
    ToolParameter,
    ToolSchemaRegistry,
    SYNAPSE_TOOLS,
    PROTOCOL_VERSION
)


class TestToolSchemaProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        assert PROTOCOL_VERSION == "1.0"
    
    def test_registry_has_protocol_version(self):
        assert ToolSchemaRegistry.PROTOCOL_VERSION == "1.0"
    
    def test_parameter_has_protocol_version(self):
        param = ToolParameter(name="test", type="string", description="test")
        assert param.protocol_version == "1.0"
    
    def test_schema_has_protocol_version(self):
        schema = ToolSchema(
            name="test",
            description="test",
            parameters=[]
        )
        assert schema.protocol_version == "1.0"


class TestToolSchema:
    """Tests for ToolSchema."""
    
    def test_to_anthropic_format(self):
        schema = ToolSchema(
            name="test_tool",
            description="Test tool",
            parameters=[
                ToolParameter(name="param1", type="string", description="Test param")
            ]
        )
        anthropic = schema.to_anthropic_format()
        assert anthropic["name"] == "test_tool"
        assert "input_schema" in anthropic
    
    def test_to_openai_format(self):
        schema = ToolSchema(
            name="test_tool",
            description="Test tool",
            parameters=[]
        )
        openai = schema.to_openai_format()
        assert openai["type"] == "function"
        assert openai["function"]["name"] == "test_tool"


class TestToolSchemaRegistry:
    """Tests for ToolSchemaRegistry."""
    
    @pytest.fixture
    def registry(self):
        return ToolSchemaRegistry()
    
    def test_register_tool(self, registry):
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters=[]
        )
        registry.register(schema)
        assert "test" in registry.list_tools()
    
    def test_get_tool(self, registry):
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters=[]
        )
        registry.register(schema)
        retrieved = registry.get("test")
        assert retrieved.name == "test"
    
    def test_to_anthropic_tools(self, registry):
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters=[]
        )
        registry.register(schema)
        tools = registry.to_anthropic_tools()
        assert len(tools) == 1
    
    def test_validate_schema_missing_name(self, registry):
        schema = ToolSchema(
            name="",
            description="Test",
            parameters=[]
        )
        with pytest.raises(ValueError):
            registry._validate_schema(schema)


class TestSynapseTools:
    """Tests for pre-defined Synapse tools."""
    
    def test_synapse_tools_exist(self):
        assert len(SYNAPSE_TOOLS) >= 3
    
    def test_synapse_tools_have_protocol_version(self):
        for tool in SYNAPSE_TOOLS:
            assert tool.protocol_version == "1.0"


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        from synapse.integrations.tool_schema import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
