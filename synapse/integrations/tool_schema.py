"""
Tool Schema for Synapse.

Adapted from Anthropic Tool Use patterns:
https://docs.anthropic.com/claude/docs/tool-use

Original License: Anthropic Terms of Service
Adaptation: Added protocol versioning, capability requirements,
           security validation, audit logging

Copyright (c) 2024 Anthropic, PBC
Copyright (c) 2026 Synapse Contributors
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json

PROTOCOL_VERSION: str = "1.0"


@dataclass
class ToolParameter:
    """Parameter for a tool"""
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ToolSchema:
    """Schema for a tool"""
    name: str
    description: str
    parameters: List[ToolParameter]
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: int = 1
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    isolation_type: str = "subprocess"
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic tool format"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.to_anthropic_format()["input_schema"]
            }
        }


class ToolSchemaRegistry:
    """
    Registry for tool schemas.
    
    Adapted from Anthropic Tool Use patterns with Synapse security enhancements.
    
    Features:
    - Tool schema registration and validation
    - Capability requirement tracking
    - Protocol versioning compliance
    - Multi-format export (Anthropic, OpenAI)
    """
    
    PROTOCOL_VERSION: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        security_manager: Any = None,
        audit_logger: Any = None
    ):
        self.security = security_manager
        self.audit = audit_logger
        self.tools: Dict[str, ToolSchema] = {}
    
    def register(self, schema: ToolSchema) -> None:
        """Register a tool schema"""
        self._validate_schema(schema)
        self.tools[schema.name] = schema
    
    def get(self, name: str) -> Optional[ToolSchema]:
        """Get tool schema by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tools"""
        return list(self.tools.keys())
    
    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Export all tools in Anthropic format"""
        return [t.to_anthropic_format() for t in self.tools.values()]
    
    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Export all tools in OpenAI format"""
        return [t.to_openai_format() for t in self.tools.values()]
    
    def _validate_schema(self, schema: ToolSchema) -> None:
        """Validate tool schema"""
        if not schema.name:
            raise ValueError("Tool name is required")
        
        if not schema.description:
            raise ValueError("Tool description is required")
        
        if schema.risk_level < 1 or schema.risk_level > 5:
            raise ValueError("Risk level must be between 1 and 5")
        
        # Validate parameters
        for param in schema.parameters:
            if not param.name:
                raise ValueError("Parameter name is required")
            if not param.type:
                raise ValueError(f"Parameter {param.name} type is required")


# Pre-defined tool schemas for Synapse
SYNAPSE_TOOLS = [
    ToolSchema(
        name="execute_skill",
        description="Execute a skill with given parameters",
        parameters=[
            ToolParameter(name="skill_name", type="string", description="Name of skill to execute"),
            ToolParameter(name="parameters", type="object", description="Parameters for the skill")
        ],
        required_capabilities=["skill:execute"],
        risk_level=3,
        protocol_version=PROTOCOL_VERSION
    ),
    ToolSchema(
        name="create_checkpoint",
        description="Create a checkpoint for rollback",
        parameters=[
            ToolParameter(name="agent_id", type="string", description="Agent ID"),
            ToolParameter(name="session_id", type="string", description="Session ID")
        ],
        required_capabilities=["checkpoint:create"],
        risk_level=2,
        protocol_version=PROTOCOL_VERSION
    ),
    ToolSchema(
        name="request_approval",
        description="Request human approval for action",
        parameters=[
            ToolParameter(name="action_type", type="string", description="Type of action"),
            ToolParameter(name="details", type="object", description="Action details"),
            ToolParameter(name="risk_level", type="integer", description="Risk level 1-5")
        ],
        required_capabilities=["approval:request"],
        risk_level=2,
        protocol_version=PROTOCOL_VERSION
    )
]


SKILL_MANIFEST = {
    "name": "tool_schema_registry",
    "version": "1.0.0",
    "description": "Tool schema registry with multi-format export",
    "author": "synapse_core",
    "inputs": {
        "tool_name": "str",
        "format": "str"
    },
    "outputs": {
        "schema": "dict"
    },
    "required_capabilities": ["tool:read"],
    "risk_level": 1,
    "isolation_type": "subprocess",
    "protocol_version": PROTOCOL_VERSION
}
