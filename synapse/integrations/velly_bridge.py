"""Deprecated Velly compatibility shim.

Velly is no longer consulted by Synapse. OpenCode is the primary runtime for
models, and external coding-agent CLIs are discovered directly from the machine
(see :mod:`synapse.integrations.external_agents`). This module stays only so
older imports keep working; it performs no Velly filesystem or configuration
reads.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

from typing import Any

from synapse.integrations.external_agents import (
    ExternalAgent,
    detect_agents,
    sync_agents_to_control_plane,
)
from synapse.integrations.opencode_bridge import (
    OpenCodeModel,
    detect_models,
    find_opencode_cli,
    list_opencode_models,
    opencode_status,
    preferred_model,
    quota_status,
)

# Compatibility aliases: older callers imported these names from this module.
VellyAgent = ExternalAgent
VellyModel = OpenCodeModel


def velly_legacy_status() -> dict[str, Any]:
    """Return the removed-Velly status without reading any Velly data."""
    return {
        "status": "removed",
        "deprecated": True,
        "removed": True,
        "replacement": "opencode",
        "agents": [agent.to_dict() for agent in detect_agents()],
        "workspaces": [],
        "chat_config": {},
        "note": "Velly has been replaced by OpenCode; no Velly state is read.",
        "protocol_version": PROTOCOL_VERSION,
    }


def velly_status() -> dict[str, Any]:
    """Backward-compatible combined status (removed Velly + OpenCode)."""
    legacy = velly_legacy_status()
    opencode = opencode_status()
    return {
        **legacy,
        "models": opencode.get("models", []),
        "opencode_cli": opencode.get("cli"),
        "opencode": opencode,
        "quota": opencode.get("quota", quota_status()),
    }


__all__ = [
    "VellyAgent",
    "VellyModel",
    "detect_agents",
    "detect_models",
    "find_opencode_cli",
    "list_opencode_models",
    "preferred_model",
    "quota_status",
    "sync_agents_to_control_plane",
    "velly_legacy_status",
    "velly_status",
]
