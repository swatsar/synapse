"""Typed runtime settings and one-time ``.env`` loading.

The application has historically read environment variables ad hoc from many
modules. This module gives the runtime a single, typed view of the settings
that affect safety-critical behaviour (local-only routing, default model,
workspace root and the human-approval risk threshold) and loads a local
``.env`` file exactly once per process.

Nothing here overrides an environment variable that the operator (or a test)
already set: explicit process configuration always wins over the file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from threading import Lock

PROTOCOL_VERSION: str = "1.0"

_TRUTHY = {"1", "true", "yes", "on"}
_load_lock = Lock()
_env_loaded = False


def _flag(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in _TRUTHY


def load_env(path: str | Path | None = None, *, override: bool = False) -> bool:
    """Load ``.env`` once per process without clobbering explicit settings.

    Returns ``True`` when a file was loaded. Missing ``python-dotenv`` or a
    missing file is not an error: the runtime must still start from real
    process environment variables.
    """
    global _env_loaded
    with _load_lock:
        if _env_loaded:
            return False
        _env_loaded = True

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is declared
        return False

    target = Path(path).expanduser() if path is not None else None
    return bool(load_dotenv(dotenv_path=target, override=override))


def local_only_enabled() -> bool:
    """Return the effective local-only policy from the current environment.

    Read on every call so an operator (or a test) can change the policy for a
    process without restarting it. ``SYNAPSE_FORCE_LOCAL`` is kept as an alias
    because it was introduced by the router before the typed settings existed.
    """
    return _flag(os.getenv("SYNAPSE_LOCAL_ONLY")) or _flag(
        os.getenv("SYNAPSE_FORCE_LOCAL")
    )


def selected_opencode_enabled() -> bool:
    """Whether a user-selected OpenCode chat may use its provider."""
    return _flag(os.getenv("SYNAPSE_ALLOW_SELECTED_OPENCODE"))


def selected_opencode_model(metadata: dict) -> str | None:
    if not selected_opencode_enabled() or any(
        metadata.get(key) for key in ("local_only", "privacy", "executor")
    ):
        return None
    model = metadata.get("model")
    return model if isinstance(model, str) and model.startswith("opencode/") else None


def configured_default_model() -> str:
    """Return the operator's preferred default model, if configured."""
    value = (os.getenv("SYNAPSE_DEFAULT_MODEL") or "").strip()
    return value or "claude-sonnet-5-5"


def approval_risk_threshold() -> int:
    """Return the risk level at which human approval is required (1..5).

    Read on every call so the threshold remains operator-configurable without
    a restart. Invalid or out-of-range values fall back to the documented
    default of 3 rather than disabling the approval gate.
    """
    try:
        threshold = int(os.getenv("SYNAPSE_APPROVAL_RISK_THRESHOLD", "3"))
    except ValueError:
        threshold = 3
    return min(5, max(1, threshold))


def approval_ttl_seconds() -> int:
    """Lifetime of a pending action approval, in seconds (30s..24h)."""
    try:
        ttl = int(os.getenv("SYNAPSE_APPROVAL_TTL_SECONDS", "900"))
    except ValueError:
        ttl = 900
    return min(86400, max(30, ttl))


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable snapshot of safety-critical runtime configuration."""

    local_only: bool = False
    default_model: str = "claude-sonnet-5-5"
    workspace_root: str = "."
    approval_risk_threshold: int = 3
    approval_ttl_seconds: int = 900
    protocol_version: str = PROTOCOL_VERSION

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            local_only=local_only_enabled(),
            default_model=configured_default_model(),
            workspace_root=os.getenv("SYNAPSE_WORKSPACE_ROOT", "."),
            approval_risk_threshold=approval_risk_threshold(),
            approval_ttl_seconds=approval_ttl_seconds(),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached startup settings, loading ``.env`` first."""
    load_env()
    return Settings.from_env()


def reload_settings() -> Settings:
    """Drop the cache and re-read the environment (used after explicit changes)."""
    get_settings.cache_clear()
    return get_settings()


def reset_env_loader() -> None:
    """Allow a test to exercise ``load_env`` again in the same process."""
    global _env_loaded
    with _load_lock:
        _env_loaded = False
