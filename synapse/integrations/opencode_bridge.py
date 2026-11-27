"""OpenCode-first discovery, model catalog and runtime health.

OpenCode is Synapse's primary external model runtime. This module owns CLI
discovery, model enumeration and the short-lived health cache that stops the
router from hammering a runtime whose free quota is exhausted.

No other application's model catalog is consulted here. External coding-agent
CLIs are discovered independently by
:mod:`synapse.integrations.external_agents`.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Free OpenCode models are account-wide, so a quota failure is worth caching for
# minutes instead of retrying on every chat message. Operators can shorten the
# cooldown for testing.
_DEFAULT_QUOTA_COOLDOWN = 900.0
_DEFAULT_ERROR_COOLDOWN = 60.0
_MODEL_CACHE_TTL = 60.0

_QUOTA_MARKERS = (
    "free usage limit reached",
    "usage limit reached",
    "usage limit",
    "subscription required",
    "subscribe to opencode go",
    "quota exceeded",
    "quota exhausted",
    "insufficient credits",
    "credit balance",
    "rate limit exceeded",
    "too many requests",
    "429",
)

_TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "connection",
    "network",
    "temporarily unavailable",
    "service unavailable",
    "could not be started",
)


@dataclass(frozen=True)
class OpenCodeModel:
    """One model exposed by the local OpenCode runtime."""

    model_id: str
    display_name: str
    provider: str = "opencode"
    group: str = "OpenCode"
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.model_id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "group": self.group,
            "available": self.available,
            "protocol_version": PROTOCOL_VERSION,
        }


@dataclass
class _HealthState:
    last_error: str | None = None
    last_error_at: float = 0.0
    quota_message: str | None = None
    quota_until: float = 0.0
    model_quotas: dict[str, tuple[float, str]] = field(default_factory=dict)


_HEALTH = _HealthState()
_HEALTH_LOCK = threading.Lock()
# Quota errors from custom agent configurations do not apply to stock Build.
_HEALTH_CACHE_VERSION = 3
_MODEL_CACHE: tuple[float, list[str]] = (0.0, [])


def _health_path() -> Path:
    override = os.getenv("SYNAPSE_OPENCODE_HEALTH_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    root = os.getenv("SYNAPSE_WORKSPACE_ROOT", "").strip() or os.getcwd()
    return Path(root) / ".synapse" / "opencode_health.json"


def _persist_health() -> None:
    """Persist the non-secret quota/error circuit across restarts."""
    try:
        with _HEALTH_LOCK:
            payload = {
                "cache_version": _HEALTH_CACHE_VERSION,
                "last_error": _HEALTH.last_error,
                "last_error_at": _HEALTH.last_error_at,
                "quota_message": _HEALTH.quota_message,
                "quota_until": _HEALTH.quota_until,
                "model_quotas": dict(_HEALTH.model_quotas),
                "profile": _profile_id(),
            }
        path = _health_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _profile_id() -> str:
    return "desktop" if os.getenv("SYNAPSE_OPENCODE_DESKTOP_DB") else "private"


def _load_health() -> None:
    try:
        data = json.loads(_health_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if (not isinstance(data, dict)
            or data.get("cache_version") != _HEALTH_CACHE_VERSION
            or data.get("profile") != _profile_id()):
        return
    now = time.time()
    with _HEALTH_LOCK:
        last_error = data.get("last_error")
        _HEALTH.last_error = str(last_error) if last_error else None
        try:
            _HEALTH.last_error_at = float(data.get("last_error_at") or 0.0)
        except (TypeError, ValueError):
            _HEALTH.last_error_at = 0.0
        try:
            quota_until = float(data.get("quota_until") or 0.0)
        except (TypeError, ValueError):
            quota_until = 0.0
        if quota_until > now:
            _HEALTH.quota_until = quota_until
            message = data.get("quota_message")
            _HEALTH.quota_message = str(message) if message else None
        else:
            _HEALTH.quota_until = 0.0
            _HEALTH.quota_message = None
        stored = data.get("model_quotas")
        if isinstance(stored, dict):
            for model_id, item in stored.items():
                if (isinstance(item, list) and len(item) == 2
                        and isinstance(item[0], (int, float)) and isinstance(item[1], str)
                        and item[0] > now):
                    _HEALTH.model_quotas[model_id] = (item[0], item[1])


_load_health()


def _quota_cooldown() -> float:
    raw = os.getenv("SYNAPSE_OPENCODE_QUOTA_COOLDOWN", "").strip()
    try:
        return max(30.0, float(raw))
    except (TypeError, ValueError):
        return _DEFAULT_QUOTA_COOLDOWN


def _error_cooldown() -> float:
    raw = os.getenv("SYNAPSE_OPENCODE_ERROR_COOLDOWN", "").strip()
    try:
        return max(5.0, float(raw))
    except (TypeError, ValueError):
        return _DEFAULT_ERROR_COOLDOWN


def classify_opencode_error(error: Any) -> str:
    """Classify a provider failure as ``quota``, ``transient`` or ``other``."""
    message = str(error or "").lower()
    if not message:
        return "other"
    if any(marker in message for marker in _QUOTA_MARKERS):
        return "quota"
    if any(marker in message for marker in _TRANSIENT_MARKERS):
        return "transient"
    return "other"


def record_opencode_failure(error: Any, *, model_id: str | None = None) -> str:
    """Remember the latest OpenCode failure and start a cooldown when needed."""
    message = str(error or "OpenCode request failed").strip()[:2000]
    kind = classify_opencode_error(message)
    now = time.time()
    with _HEALTH_LOCK:
        _HEALTH.last_error = message
        _HEALTH.last_error_at = now
        if kind == "quota":
            until = now + _quota_cooldown()
            if model_id:
                _HEALTH.model_quotas[model_id] = (until, message)
            else:
                _HEALTH.quota_message = message
                _HEALTH.quota_until = until
        # Transient/other failures stay visible through ``last_error`` for the
        # error cooldown, but they must not masquerade as quota exhaustion.
    _persist_health()
    try:
        from synapse.observability.logger import audit

        audit(
            event="opencode_failure",
            model_id=model_id,
            kind=kind,
            error=message[:500],
            cooldown_seconds=(
                _quota_cooldown() if kind == "quota" else _error_cooldown()
            ),
        )
    except Exception:  # observability must never break model fallback
        pass
    return kind


def record_opencode_success(*, model_id: str | None = None) -> None:
    """Clear cached failures after a successful OpenCode response."""
    with _HEALTH_LOCK:
        _HEALTH.last_error = None
        _HEALTH.last_error_at = 0.0
        if model_id:
            _HEALTH.model_quotas.pop(model_id, None)
        else:
            _HEALTH.quota_message = None
            _HEALTH.quota_until = 0.0
            _HEALTH.model_quotas.clear()
    _persist_health()


def reset_opencode_health() -> dict[str, Any]:
    """Clear the circuit state so an operator can retry immediately."""
    record_opencode_success()
    return quota_status()


def quota_status(model_id: str | None = None) -> dict[str, Any]:
    """Return a model cooldown or the explicitly recorded provider-wide cooldown."""
    now = time.time()
    with _HEALTH_LOCK:
        until, message = _HEALTH.quota_until, _HEALTH.quota_message
        if model_id:
            model_until, model_message = _HEALTH.model_quotas.get(model_id, (0.0, None))
            if model_until > until:
                until, message = model_until, model_message
        remaining = max(0.0, until - now)
        return {
            "exhausted": remaining > 0,
            "message": message if remaining else None,
            "retry_after_seconds": int(remaining + 0.999) if remaining else 0,
            "reset_at": until if remaining else None,
            "protocol_version": PROTOCOL_VERSION,
        }


def is_opencode_quota_exhausted(model_id: str | None = None) -> bool:
    return bool(quota_status(model_id)["exhausted"])


def last_opencode_error() -> str | None:
    with _HEALTH_LOCK:
        if not _HEALTH.last_error:
            return None
        age = time.time() - _HEALTH.last_error_at
        return _HEALTH.last_error if age <= _error_cooldown() else None


# The first `opencode.exe` on PATH is not necessarily the real OpenCode
# runtime: pnpm/npm shims for unrelated vendored CLIs also use that name. A
# candidate is only trusted after `models` returns at least one model id.
_WORKING_CLI: Path | None = None
_MODEL_PROBE_CACHE: dict[str, tuple[float, list[str]]] = {}
_MODEL_PROBE_TTL = 60.0


def _opencode_cli_candidates() -> list[Path]:
    """Return every existing OpenCode CLI candidate, best guess first."""
    candidates: list[Path] = []

    def add(value: Path | str | None) -> None:
        if not value:
            return
        try:
            candidate = Path(value).expanduser()
            if candidate.is_file() and candidate not in candidates:
                candidates.append(candidate)
        except OSError:
            return

    override = os.getenv("SYNAPSE_OPENCODE_CLI", "").strip()
    if override:
        add(override)
    for name in ("opencode", "opencode-ai", "opencode.exe", "opencode-cli.exe"):
        add(shutil.which(name))

    local_appdata = os.getenv("LOCALAPPDATA", "")
    appdata = os.getenv("APPDATA", "")
    program_files = os.getenv("ProgramFiles", "")
    program_files_x86 = os.getenv("ProgramFiles(x86)", "")
    chocolatey = os.getenv("ChocolateyInstall", "")
    roots: list[Path] = []
    if local_appdata:
        roots.extend([
            # Standalone OpenCode installs come first; a desktop-bundled copy
            # is only one of several possible locations.
            Path(local_appdata) / "Programs" / "opencode",
            Path(local_appdata) / "Programs" / "opencode" / "bin",
            Path(local_appdata) / "Programs" / "opencode" / "resources" / "app.asar.unpacked" / "node_modules" / "@opencode",
            Path(local_appdata) / "Programs" / "@opencode-aidesktop" / "resources" / "app.asar.unpacked" / "node_modules" / "@opencode",
            Path(local_appdata) / "opencode",
            Path(local_appdata) / "@opencode",
            Path(local_appdata) / "Microsoft" / "WinGet" / "Links",
            # Do not walk the pnpm store recursively: it can contain hundreds
            # of megabytes and several unrelated `opencode` shims. A pnpm
            # install is already covered by ``shutil.which`` above.
        ])
    if appdata:
        desktop_cli = Path(appdata) / "ai.opencode.desktop" / "cli"
        installs = []
        try:
            for install in desktop_cli.iterdir():
                version = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)-(x64|arm64|ia32)", install.name)
                if version:
                    installs.append((tuple(map(int, version.groups()[:3])), install.name, install))
        except OSError:
            pass
        for _, _, install in sorted(installs, reverse=True):
            add(install / "opencode-cli.exe")
        roots.extend([
            Path(appdata) / "opencode",
            Path(appdata) / "npm",
        ])
    if program_files:
        roots.append(Path(program_files) / "opencode")
    if program_files_x86:
        roots.append(Path(program_files_x86) / "opencode")
    if chocolatey:
        roots.append(Path(chocolatey) / "bin")
    home = Path.home()
    roots.extend([
        home / ".opencode" / "bin",
        home / ".opencode",
        home / ".local" / "bin",
        home / "scoop" / "shims",
        home / "AppData" / "Local" / "opencode",
        # Last resort: older desktop bundles shipped the OpenCode CLI inside
        # another app's install tree. This is a CLI location only; no Velly
        # state, configuration or models are read.
        home / "AppData" / "Local" / "Programs" / "velly" / "resources" / "app.asar.unpacked" / "node_modules" / "@opencode",
        home / "AppData" / "Roaming" / "Velly" / "agent-tools" / "node_modules" / "@opencode",
    ])
    if local_appdata:
        roots.append(
            Path(local_appdata) / "Programs" / "velly" / "resources" / "app.asar.unpacked" / "node_modules" / "@opencode"
        )
    if appdata:
        roots.append(Path(appdata) / "Velly" / "agent-tools" / "node_modules" / "@opencode")

    # Deliberately not recursive: `**/opencode.exe` crawled the whole desktop
    # app bundle and the pnpm store, turning one status request into a 49-96 s
    # stall. Standard layouts are covered below; unusual installs can point
    # SYNAPSE_OPENCODE_CLI at the binary.
    patterns = (
        "opencode.exe",
        "opencode",
        "*/bin/opencode.exe",
        "*/bin/opencode",
        "cli-*/bin/opencode.exe",
        "cli-*/bin/opencode",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            try:
                for candidate in sorted(root.glob(pattern)):
                    add(candidate)
            except OSError:
                continue
    return candidates


def opencode_child_environment() -> dict[str, str]:
    """Do not give the OpenCode child Synapse's API or storage secrets."""
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("SYNAPSE_")}
    # The vendor CLI resolves its own credentials. Synapse never opens the database.
    desktop_db = os.getenv("SYNAPSE_OPENCODE_DESKTOP_DB")
    desktop_cache = os.getenv("SYNAPSE_OPENCODE_DESKTOP_CACHE")
    if desktop_db:
        env["OPENCODE_DB"] = desktop_db
    if desktop_cache:
        env["XDG_CACHE_HOME"] = desktop_cache
    return env


def _read_cli_models(cli: Path, *, force: bool = False) -> list[str]:
    """Ask one CLI for its model catalog, caching the parsed result."""
    key = str(cli)
    now = time.monotonic()
    if not force:
        cached = _MODEL_PROBE_CACHE.get(key)
        if cached and now < cached[0]:
            return list(cached[1])
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    models: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="synapse-opencode-models-") as workdir:
            completed = subprocess.run(
                [str(cli), "models", "--standalone", "--log-level", "none"],
                executable=str(cli),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                cwd=workdir,
                env=opencode_child_environment(),
                creationflags=creationflags,
            )
        for line in (completed.stdout or "").splitlines():
            value = line.strip()
            if not value or "/" not in value or " " in value or "\t" in value:
                continue
            if value.startswith("#"):
                continue
            if value not in models:
                models.append(value)
    except (OSError, subprocess.SubprocessError):
        models = []
    models.sort()
    _MODEL_PROBE_CACHE[key] = (now + _MODEL_PROBE_TTL, models)
    return list(models)


def find_opencode_cli() -> Path | None:
    """Locate a *working* OpenCode CLI from an override, PATH or installs.

    Candidates that do not answer ``models`` with a real catalog (for example
    an unrelated ``opencode`` shim shipped by another package) are skipped.
    """
    global _WORKING_CLI
    # A verified binary is reused without another filesystem walk. The probe
    # is the expensive part; the path itself is stable for this process.
    if _WORKING_CLI is not None:
        try:
            if _WORKING_CLI.is_file():
                return _WORKING_CLI
        except OSError:
            pass
        _WORKING_CLI = None
    candidates = _opencode_cli_candidates()
    if not candidates:
        return None
    for candidate in candidates:
        if _read_cli_models(candidate):
            _WORKING_CLI = candidate
            return candidate
    # No candidate proved functional. Preserve the old first-match contract so
    # callers (and tests with stand-in binaries) still receive a path.
    _WORKING_CLI = None
    return candidates[0]


def _configured_models() -> list[str]:
    """Models pinned by an explicit operator override, if any."""
    raw = os.getenv("SYNAPSE_OPENCODE_MODELS", "").strip()
    if not raw:
        return []
    models: list[str] = []
    for item in raw.replace(";", ",").split(","):
        value = item.strip()
        if value and "/" in value and value not in models:
            models.append(value)
    return models


def list_opencode_models(force: bool = False) -> list[str]:
    """Return model ids reported by the local OpenCode runtime (cached)."""
    global _MODEL_CACHE
    configured = _configured_models()
    if configured:
        return sorted(configured)

    now = time.monotonic()
    cached_at, cached = _MODEL_CACHE
    if not force and cached and now - cached_at < _MODEL_CACHE_TTL:
        return list(cached)

    cli = find_opencode_cli()
    if cli is None:
        _MODEL_CACHE = (now, [])
        return []

    models = _read_cli_models(cli, force=force)
    _MODEL_CACHE = (now, models)
    return list(models)


def detect_models() -> list[OpenCodeModel]:
    """List the OpenCode models that can be routed through Synapse."""
    models: list[OpenCodeModel] = []
    seen: set[str] = set()
    for model_id in list_opencode_models():
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        leaf = model_id.split("/", 1)[-1]
        display = leaf.replace("-", " ").replace("_", " ").strip().title()
        models.append(OpenCodeModel(
            model_id=model_id, display_name=display or model_id,
            available=not is_opencode_quota_exhausted(model_id),
        ))
    return models


def preferred_model() -> str | None:
    """Deterministic free model for automatic chat, or ``None`` in cooldown."""
    if is_opencode_quota_exhausted():
        return None
    available = [model for model in list_opencode_models() if not is_opencode_quota_exhausted(model)]
    if not available:
        return None
    preferred = "opencode/deepseek-v4.1-flash-free"
    return preferred if preferred in available else available[0]


def opencode_status(*, include_models: bool = True) -> dict[str, Any]:
    """Truthful OpenCode status for the API and UI.

    ``status`` is one of ``ready``, ``quota_exhausted``, ``degraded`` or
    ``not_found``. It never claims readiness just because a path exists.
    """
    cli = find_opencode_cli()
    model_ids = list_opencode_models() if cli else []
    quota = quota_status()
    last_error = last_opencode_error()

    if cli is None:
        status = "not_found"
    elif quota["exhausted"]:
        status = "quota_exhausted"
    elif model_ids:
        status = "ready"
    else:
        status = "degraded"

    result: dict[str, Any] = {
        "runtime": "opencode",
        "status": status,
        "cli": str(cli) if cli else None,
        "model_ids": model_ids,
        "model_count": len(model_ids),
        "model_quotas": {} if quota["exhausted"] else {
            model_id: model_quota for model_id in model_ids
            if (model_quota := quota_status(model_id))["exhausted"]
        },
        "quota": quota,
        "last_error": last_error,
        "preferred_model": preferred_model(),
        "catalog_source": "opencode_cli",
        "protocol_version": PROTOCOL_VERSION,
    }
    if include_models:
        result["models"] = [model.to_dict() for model in detect_models()]
    return result


__all__ = [
    "OpenCodeModel",
    "classify_opencode_error",
    "detect_models",
    "find_opencode_cli",
    "is_opencode_quota_exhausted",
    "last_opencode_error",
    "list_opencode_models",
    "opencode_status",
    "preferred_model",
    "quota_status",
    "record_opencode_failure",
    "record_opencode_success",
    "reset_opencode_health",
]
