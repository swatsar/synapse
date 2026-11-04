"""Operator-facing integration inventory for MCP, plugins, and executors."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from synapse.harnesses import ClaudeCodeHarness, CodexHarness

router = APIRouter()


@router.get("")
async def integration_inventory() -> dict[str, Any]:
    """Expose truthful capabilities and configuration state to the UI."""
    return {
        "mcp": {
            "status": "registry_available",
            "configured_servers": 0,
            "transports": ["stdio", "streamable_http"],
            "note": "MCP registry exists; persisted server management and live SDK connections are not yet enabled.",
        },
        "plugins": {
            "status": "runtime_available",
            "configured_plugins": 0,
            "note": "Plugin manifests/runtime exist; UI installation and activation flow is not yet enabled.",
        },
        "executors": [
            {
                "id": "codex",
                "status": "opt_in_cli_adapter",
                "configured": CodexHarness().enabled,
                "safe_mode": "read-only",
                "supports": ["jsonl", "timeout", "process_cleanup"],
            },
            {
                "id": "claude_code",
                "status": "opt_in_cli_adapter",
                "configured": ClaudeCodeHarness().enabled,
                "safe_mode": "dontAsk + Read/Glob/Grep",
                "supports": ["stream-json", "timeout", "process_cleanup"],
            },
        ],
        "vally": {
            "status": "not_configured",
            "note": "No Velly agent protocol is configured in this runtime; browser QA is separate from an executor integration.",
        },
        "protocol_version": "1.0",
    }


__all__ = ["router"]
